package amtw;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import com.bitwig.extension.api.opensoundcontrol.OscAddressSpace;
import com.bitwig.extension.api.opensoundcontrol.OscConnection;
import com.bitwig.extension.api.opensoundcontrol.OscModule;
import com.bitwig.extension.controller.ControllerExtension;
import com.bitwig.extension.controller.ControllerExtensionDefinition;
import com.bitwig.extension.controller.api.Clip;
import com.bitwig.extension.controller.api.ClipLauncherSlot;
import com.bitwig.extension.controller.api.ClipLauncherSlotBank;
import com.bitwig.extension.controller.api.ControllerHost;
import com.bitwig.extension.controller.api.CursorTrack;
import com.bitwig.extension.controller.api.DocumentState;
import com.bitwig.extension.controller.api.NoteStep;
import com.bitwig.extension.controller.api.SettableEnumValue;
import com.bitwig.extension.controller.api.Signal;

/**
 * Sends the selected clip's notes to the workbench, and takes edits back.
 *
 * The problem this exists for: reading an analysis in one window and typing
 * notes into another means a mouse slip lands silently and is discovered much
 * later, usually after being built on. So the clip is observed live, the
 * analysis happens outside Bitwig, and anything worth saying comes back as a
 * popup *in* Bitwig while your hand is still on the note.
 *
 * Two deliberate choices:
 *
 * Sending is DEBOUNCED. addNoteStepObserver fires per step, so dragging a note
 * across an octave produces a burst of callbacks; analysing each one would be
 * noise. Edits settle for {@value #SETTLE_MS} ms before anything is sent.
 *
 * Nothing is written unless asked. The bridge can call /amtw/setStep, but the
 * workbench only sends that in response to an explicit action — this extension
 * never "corrects" anything on its own. A tool that silently rewrites your take
 * is worse than no tool.
 */
public class AmtwHarmonyExtension extends ControllerExtension
{
   private static final String HOST = "127.0.0.1";
   private static final int SEND_PORT = 8732;      // workbench listens here

   /** First port we try to listen on, and how many to try after it.
    *
    * OscServer exposes start(int) and nothing else -- there is no close. So a
    * server bound by one instance of this extension stays bound for the life
    * of the Bitwig process, and REMOVING AND RE-ADDING THE CONTROLLER made
    * every later instance die in init() with BindException, taking the whole
    * control surface with it. Restarting Bitwig was the only cure.
    *
    * So take the next free port instead, and tell the workbench which one it
    * was. The bridge sweeps the same range, so it finds us wherever we land. */
   private static final int RECV_PORT_BASE = 8733;
   private static final int RECV_PORT_TRIES = 10;
   private static final int SETTLE_MS = 250;
   private static final int TICK_MS = 100;

   /** Steps and keys the cursor clip exposes: 128 steps at 1/16 is 8 bars.
    *
    * This was 512 x 128, and sendClip() walked every cell with getStep().
    * That is 65,536 API calls in one pass on Bitwig's controller thread, which
    * stalled it hard enough to take Bitwig down and meant no clip was ever
    * sent. Notes are now tracked incrementally from the observer and the grid
    * is never scanned, so this bound only limits how much clip is visible --
    * but it stays modest, because the observer fires per cell too. */
   private static final int GRID_STEPS = 128;
   private static final int GRID_KEYS = 128;

   /** The bridge's note payload. A JSON library would be a dependency for one
    *  fixed shape that this repo produces itself; a scanner over a known
    *  format is smaller than the argument for adding one. */
   private static final Pattern NOTE_RE = Pattern.compile(
      "\\{\"x\":(-?\\d+),\"y\":(-?\\d+),\"vel\":(-?\\d+),\"dur\":(-?[\\d.]+)\\}");

   private ControllerHost mHost;
   private Clip mClip;
   private OscConnection mOut;
   private CursorTrack mTrack;
   private ClipLauncherSlotBank mSlots;
   private SettableEnumValue mMode;

   /** Notes waiting for a freshly-created clip to become the cursor clip.
    *  Bitwig's API is asynchronous: selecting a slot does not repoint the
    *  cursor clip in the same call, so writes are deferred a beat. */
   private String mPendingNotes = null;
   private int mPendingTries = 0;

   private boolean mDirty = false;
   private long mLastChange = 0;
   private boolean mConnected = false;
   private boolean mLoggedStates = false;
   private int mInPort = -1;                   // the port we actually got

   /** (x<<16|y) -> {x, y, velocity, duration}, kept up to date by the note
    *  step observer so a send never has to read the clip back. */
   private final java.util.TreeMap<Long, double[]> mSteps = new java.util.TreeMap<>();

   protected AmtwHarmonyExtension(final ControllerExtensionDefinition definition,
                                  final ControllerHost host)
   {
      super(definition, host);
      // getHost() is declared on Extension and returns the narrower Host type,
      // so keep the ControllerHost we were handed rather than casting later.
      mHost = host;
   }

   @Override
   public void init()
   {
      final OscModule osc = mHost.getOscModule();

      // inbound: the workbench asking us to say something or change something
      final OscAddressSpace in = osc.createAddressSpace();
      in.setName("amtw-in");
      in.registerMethod("/amtw/notify", ",s", "show a popup in Bitwig",
         (source, message) -> mHost.showPopupNotification(message.getString(0)));
      in.registerMethod("/amtw/log", ",s", "write to the controller console",
         (source, message) -> mHost.println(message.getString(0)));
      in.registerMethod("/amtw/setStep", ",iiid", "set one note",
         (source, message) -> setStep(message.getInt(0), message.getInt(1),
                                      message.getInt(2), message.getDouble(3)));
      in.registerMethod("/amtw/clearStep", ",ii", "clear one note",
         (source, message) -> clearStep(message.getInt(0), message.getInt(1)));
      in.registerMethod("/amtw/resend", ",", "send the clip again",
         (source, message) -> { mDirty = true; mLastChange = 0; });
      in.registerMethod("/amtw/newClip", ",sis", "put a result in a new clip",
         (source, message) -> newClip(message.getString(0), message.getInt(1),
                                      message.getString(2)));

      // Never let a busy port kill init. Losing the inbound channel is a
      // degradation; failing to start is the whole control surface gone.
      for (int i = 0; i < RECV_PORT_TRIES; i++)
      {
         final int port = RECV_PORT_BASE + i;
         try
         {
            osc.createUdpServer(port, in);
            mInPort = port;
            break;
         }
         catch (final Exception e)
         {
            // in use, almost always by a previous instance of this extension
            // in this same Bitwig process; try the next one
         }
      }
      if (mInPort < 0)
         mHost.errorln("amtw: no free port in " + RECV_PORT_BASE + "-"
                       + (RECV_PORT_BASE + RECV_PORT_TRIES - 1)
                       + "; the workbench cannot send results back");

      // outbound
      final OscAddressSpace out = osc.createAddressSpace();
      out.setName("amtw-out");
      try
      {
         mOut = osc.connectToUdpServer(HOST, SEND_PORT, out);
         mConnected = true;
      }
      catch (final Exception e)
      {
         // The workbench may simply not be running, which is normal and not
         // worth a popup every time Bitwig starts. Stay quiet and keep working.
         mHost.println("amtw: no workbench on " + HOST + ":" + SEND_PORT
                       + " — analysis is off until `amtw bitwig-bridge` runs");
         mConnected = false;
      }

      mClip = mHost.createArrangerCursorClip(GRID_STEPS, GRID_KEYS);
      mClip.setStepSize(0.25);                    // 1/16 note grid
      // Record each step as Bitwig reports it, instead of scanning for them
      // later. Bitwig re-reports the whole grid when the cursor moves to a new
      // clip, so the map corrects itself on selection without a rescan.
      mClip.addNoteStepObserver(step -> {
         final long key = ((long) step.x() << 16) | step.y();
         if ("NoteOn".equals(String.valueOf(step.state())))
            mSteps.put(key, new double[] {step.x(), step.y(),
                                          step.velocity(), step.duration()});
         else
            mSteps.remove(key);
         mDirty = true;
         mLastChange = System.currentTimeMillis();
      });
      mClip.getPlayStart().markInterested();
      mClip.getLoopLength().markInterested();

      mTrack = mHost.createCursorTrack(0, 0);
      mSlots = mTrack.clipLauncherSlotBank();
      // Casts because ecj sees Bank.getItemAt() erased to ObjectProxy: it is
      // reading the API classes from a directory (Bitwig's JRE has no
      // jdk.zipfs, so a jar classpath is unreadable) and loses the generic
      // bound. The runtime type is correct; only the compiler needs telling.
      for (int i = 0; i < mSlots.getSizeOfBank(); i++)
         slot(i).hasContent().markInterested();

      // The buttons live in the document state, so they appear in the panel
      // beside the project rather than buried in application preferences —
      // this is a per-clip action, not a setting you configure once.
      final DocumentState doc = mHost.getDocumentState();
      mMode = doc.getEnumSetting("Line", "AMTW Harmony",
                                 new String[] {"smooth", "top", "bottom"},
                                 "smooth");
      mMode.markInterested();

      final Signal reduce =
         doc.getSignalSetting("Reduce chords to one line", "AMTW Harmony",
                              "Reduce");
      reduce.addSignalObserver(() -> {
         if (!mConnected)
         {
            mHost.showPopupNotification(
               "AMTW: workbench not running — start `amtw bitwig-bridge`");
            return;
         }
         send("/amtw/reduce", mMode.get());
      });

      final Signal analyse =
         doc.getSignalSetting("What is this chord?", "AMTW Harmony", "Analyse");
      analyse.addSignalObserver(() -> {
         if (mConnected) send("/amtw/analyse", "");
         else mHost.showPopupNotification("AMTW: workbench not running");
      });

      mHost.scheduleTask(this::tick, TICK_MS);
      mHost.println("amtw harmony bridge ready (out " + SEND_PORT
                    + ", in " + (mInPort < 0 ? "NONE" : String.valueOf(mInPort))
                    + ")");
   }

   /** Poll for settled edits. Cheap, and keeps all clip reads on Bitwig's
    *  controller thread rather than an OSC callback thread. */
   private void tick()
   {
      try
      {
         if (mPendingNotes != null && --mPendingTries <= 0)
            writePending();
         else if (mDirty && mConnected && mPendingNotes == null
                  && System.currentTimeMillis() - mLastChange >= SETTLE_MS)
         {
            mDirty = false;
            sendClip();
         }
      }
      catch (final Exception e)
      {
         mHost.errorln("amtw tick: " + e);
      }
      mHost.scheduleTask(this::tick, TICK_MS);
   }

   private void sendClip()
   {
      // Serialise what the observer has already told us. No getStep() calls:
      // walking the grid was 65,536 of them per send and it took Bitwig down.
      final List<String> notes = new ArrayList<>();
      for (final double[] s : mSteps.values())
      {
         notes.add("{\"x\":" + (int) s[0] + ",\"y\":" + (int) s[1]
                   + ",\"vel\":" + fmt(s[2]) + ",\"dur\":" + fmt(s[3]) + "}");
      }
      if (!mLoggedStates)
      {
         mLoggedStates = true;
         mHost.println("amtw: first send, " + notes.size() + " notes tracked");
      }

      final StringBuilder sb = new StringBuilder(64 + notes.size() * 40);
      // inPort travels with every clip so the workbench always knows where to
      // reply, even if we landed on a fallback port
      sb.append("{\"inPort\":").append(mInPort)
        .append(",\"stepSize\":0.25,\"steps\":").append(GRID_STEPS)
        .append(",\"notes\":[");
      for (int i = 0; i < notes.size(); i++)
      {
         if (i > 0) sb.append(',');
         sb.append(notes.get(i));
      }
      sb.append("]}");

      try
      {
         mOut.sendMessage("/amtw/clip", sb.toString());
      }
      catch (final Exception e)
      {
         mHost.errorln("amtw send: " + e);
      }
   }

   private static String fmt(final double v)
   {
      return String.valueOf(Math.round(v * 1000.0) / 1000.0);
   }

   private ClipLauncherSlot slot(final int i)
   {
      return (ClipLauncherSlot) mSlots.getItemAt(i);
   }

   private void send(final String address, final String arg)
   {
      try
      {
         mOut.sendMessage(address, arg);
      }
      catch (final Exception e)
      {
         mHost.errorln("amtw send: " + e);
      }
   }

   /**
    * Put a result into a NEW clip on the current track, never into yours.
    *
    * Rejecting a result should be deleting a clip, not unwinding an edit — a
    * batch of setStep calls can land as many separate undo steps, so "undo what
    * the tool just did" would mean holding Ctrl+Z and hoping.
    */
   private void newClip(final String name, final int lengthBeats,
                        final String notesJson)
   {
      try
      {
         int idx = -1;
         for (int i = 0; i < mSlots.getSizeOfBank(); i++)
         {
            if (!slot(i).hasContent().get())
            {
               idx = i;
               break;
            }
         }
         if (idx < 0)
         {
            mHost.showPopupNotification(
               "AMTW: no empty clip slot on this track — free one and retry");
            return;
         }

         final ClipLauncherSlot target = slot(idx);
         target.createEmptyClip(Math.max(1, lengthBeats));
         target.select();
         target.showInEditor();

         // The cursor clip does not repoint within this call — Bitwig applies
         // the selection asynchronously. Hold the notes and write them a few
         // ticks later, once the cursor has actually landed on the new clip.
         mPendingNotes = notesJson;
         mPendingTries = 6;                      // ~600ms at TICK_MS
         mHost.println("amtw: created \"" + name + "\" in slot " + (idx + 1));
      }
      catch (final Exception e)
      {
         mHost.errorln("amtw newClip: " + e);
      }
   }

   private void writePending()
   {
      final String json = mPendingNotes;
      mPendingNotes = null;
      int written = 0;
      final Matcher m = NOTE_RE.matcher(json);
      while (m.find())
      {
         final int x = Integer.parseInt(m.group(1));
         final int y = Integer.parseInt(m.group(2));
         final int vel = Integer.parseInt(m.group(3));
         final double dur = Double.parseDouble(m.group(4));
         setStep(x, y, vel, dur);
         written++;
      }
      mHost.println("amtw: wrote " + written + " notes");
      mHost.showPopupNotification("AMTW: " + written + " notes in a new clip");
   }

   private void setStep(final int x, final int y, final int velocity,
                        final double duration)
   {
      try
      {
         mClip.setStep(x, y, Math.max(1, Math.min(127, velocity)), duration);
      }
      catch (final Exception e)
      {
         mHost.errorln("amtw setStep: " + e);
      }
   }

   private void clearStep(final int x, final int y)
   {
      try
      {
         mClip.clearStep(x, y);
      }
      catch (final Exception e)
      {
         mHost.errorln("amtw clearStep: " + e);
      }
   }

   @Override
   public void exit()
   {
   }

   @Override
   public void flush()
   {
   }
}
