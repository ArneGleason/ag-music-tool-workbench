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
   private static final int RECV_PORT = 8733;      // we listen here
   private static final int SETTLE_MS = 250;
   private static final int TICK_MS = 100;

   /** Steps and keys the cursor clip exposes. 128 keys is the whole MIDI
    *  range; 512 steps at 1/16 is 32 bars, which comfortably covers a section. */
   private static final int GRID_STEPS = 512;
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
      osc.createUdpServer(RECV_PORT, in);

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
      mClip.addNoteStepObserver(step -> {
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
                    + ", in " + RECV_PORT + ")");
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

   /**
    * True when a step is the START of a note rather than empty or a sustain.
    *
    * This compares the enum's name instead of writing {@code NoteStep.State.NoteOn},
    * which is a build constraint rather than a preference: the extension is
    * compiled by ecj against Bitwig's API classes unpacked to a directory
    * (Bitwig's bundled JRE has no jdk.zipfs, so a jar classpath cannot be read),
    * and ecj will not resolve the {@code NoteStep$State} nested class from a
    * directory. The trade is that an overridden toString() upstream would
    * silently match nothing — so {@link #sendClip} logs the state names it
    * actually saw, and the bridge warns if none were NoteOn.
    */
   private static boolean isNoteStart(final NoteStep s)
   {
      return s != null && "NoteOn".equals(String.valueOf(s.state()));
   }

   private void sendClip()
   {
      final List<String> notes = new ArrayList<>();
      final java.util.Set<String> statesSeen = new java.util.HashSet<>();
      for (int x = 0; x < GRID_STEPS; x++)
      {
         for (int y = 0; y < GRID_KEYS; y++)
         {
            final NoteStep s = mClip.getStep(0, x, y);
            if (s != null)
               statesSeen.add(String.valueOf(s.state()));
            if (!isNoteStart(s))
               continue;
            notes.add("{\"x\":" + x + ",\"y\":" + y
                      + ",\"vel\":" + fmt(s.velocity())
                      + ",\"dur\":" + fmt(s.duration()) + "}");
         }
      }
      if (!mLoggedStates)
      {
         mLoggedStates = true;
         mHost.println("amtw: step states seen = " + statesSeen
                       + " (expecting NoteOn among them)");
      }

      final StringBuilder sb = new StringBuilder(64 + notes.size() * 40);
      sb.append("{\"stepSize\":0.25,\"steps\":").append(GRID_STEPS)
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
