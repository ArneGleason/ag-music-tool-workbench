package amtw;

import java.util.UUID;

import com.bitwig.extension.api.PlatformType;
import com.bitwig.extension.controller.AutoDetectionMidiPortNamesList;
import com.bitwig.extension.controller.ControllerExtension;
import com.bitwig.extension.controller.ControllerExtensionDefinition;
import com.bitwig.extension.controller.api.ControllerHost;

/**
 * Registers the bridge with Bitwig.
 *
 * It declares zero MIDI ports on purpose. This is not a controller — it never
 * wants to be auto-detected against hardware, and asking for ports would make
 * Bitwig offer it a device to bind to that does not exist.
 */
public class AmtwHarmonyExtensionDefinition extends ControllerExtensionDefinition
{
   // Fixed: Bitwig keys the enabled/disabled state of a controller on this.
   // Changing it makes every existing install look like a different extension.
   private static final UUID ID =
      UUID.fromString("6f3a0d2e-9c41-4b77-a8d5-1f2b7c9e4a10");

   @Override
   public String getName()
   {
      return "AMTW Harmony Bridge";
   }

   @Override
   public String getAuthor()
   {
      return "AG Music Tool Workbench";
   }

   @Override
   public String getVersion()
   {
      return "0.1.0";
   }

   @Override
   public UUID getId()
   {
      return ID;
   }

   @Override
   public String getHardwareVendor()
   {
      return "AG Music Tool Workbench";
   }

   @Override
   public String getHardwareModel()
   {
      return "Harmony Bridge";
   }

   @Override
   public int getRequiredAPIVersion()
   {
      return 19;
   }

   @Override
   public int getNumMidiInPorts()
   {
      return 0;
   }

   @Override
   public int getNumMidiOutPorts()
   {
      return 0;
   }

   @Override
   public void listAutoDetectionMidiPortNames(
      final AutoDetectionMidiPortNamesList list, final PlatformType platformType)
   {
      // nothing: there is no hardware to detect
   }

   @Override
   public ControllerExtension createInstance(final ControllerHost host)
   {
      return new AmtwHarmonyExtension(this, host);
   }
}
