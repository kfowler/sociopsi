"""Run Socio-Psi in debug mode with console logging (no TUI)."""

import asyncio
import logging
import sys
from datetime import datetime
from sociopsi.core.agent import SocioPsiAgent


# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)


class DebugEventLogger:
    """Logs all events from the event bus."""

    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.event_counts = {}

        # Subscribe to all major events
        events_to_log = [
            "drives.updated",
            "drives.threshold_crossed",
            "perception.visual.face_detected",
            "perception.audio.ambient",
            "dialogue.archetype_voice",
            "dialogue.complete",
            "metacognition.reflection",
            "command.received",
            "command.classified",
            "command.response",
            "goal.generated",
            "goal.activated",
            "plan.created",
            "action.speak.started",
        ]

        for event in events_to_log:
            self.event_bus.subscribe(event, self._make_handler(event))

    def _make_handler(self, event_name):
        """Create event handler for specific event."""
        def handler(data):
            self.event_counts[event_name] = self.event_counts.get(event_name, 0) + 1

            # Format output based on event type
            if event_name == "drives.updated":
                logger.info(f"🔋 Drive {data['drive_name']}: {data['value']:.3f}")

            elif event_name == "drives.threshold_crossed":
                logger.warning(f"⚠️  Drive {data['drive_name']} below threshold!")

            elif event_name == "perception.visual.face_detected":
                logger.info(f"👁️  Detected {data['count']} face(s)")

            elif event_name == "perception.audio.ambient":
                logger.info(f"🔊 Audio: {data['type']} (volume: {data['volume']:.2f})")

            elif event_name == "dialogue.archetype_voice":
                logger.info(f"💭 [{data['archetype']}]: {data['voice'][:80]}...")

            elif event_name == "dialogue.complete":
                logger.info(f"🧠 [Ego]: {data['mediated_thought'][:80]}... (harmony: {data['harmony']:.2f})")

            elif event_name == "metacognition.reflection":
                logger.info(f"🪞 [Meta]: {data['reflection'][:80]}... (trend: {data['harmony_trend']})")

            elif event_name == "command.received":
                logger.info(f"📥 Command received: '{data['text']}' (source: {data['source']})")

            elif event_name == "command.classified":
                logger.info(f"🏷️  Classified as: {data['type']} - {data['intent']}")

            elif event_name == "command.response":
                logger.info(f"📤 Response: {data['text'][:80]}...")

            elif event_name == "goal.generated":
                logger.info(f"🎯 Goal generated: {data.get('description', 'Unknown')}")

            elif event_name == "action.speak.started":
                logger.info(f"🗣️  Speaking: {data.get('text', '')[:50]}...")

            else:
                logger.debug(f"Event: {event_name} - {data}")

        return handler

    def print_summary(self):
        """Print event summary."""
        logger.info("\n" + "="*60)
        logger.info("EVENT SUMMARY")
        logger.info("="*60)
        for event, count in sorted(self.event_counts.items()):
            logger.info(f"{event:40s}: {count:4d}")
        logger.info("="*60)


async def main():
    """Run agent in debug mode."""
    logger.info("="*60)
    logger.info("SOCIO-PSI DEBUG MODE")
    logger.info("="*60)
    logger.info("Starting agent with console logging...")
    logger.info("")

    # Create agent
    agent = SocioPsiAgent()

    # Set up event logging
    event_logger = DebugEventLogger(agent.event_bus)

    # Start agent
    logger.info("🚀 Starting agent systems...")
    try:
        # Start camera
        if agent.visual_perception.start_camera():
            logger.info("✅ Camera started")
        else:
            logger.warning("⚠️  Camera failed to start")

        # Start audio
        await agent.audio_perception.start()
        logger.info("✅ Audio perception started")

        # Set running flag
        agent.running = True
        logger.info("✅ Agent running\n")

        # Main loop
        logger.info("📊 Beginning main update loop (Ctrl+C to stop)...\n")

        cycle = 0
        while agent.running:
            cycle += 1

            # Log cycle marker every 10 cycles
            if cycle % 10 == 0:
                logger.info(f"--- Cycle {cycle} ---")

            # Update agent
            await agent.update()

            # Sleep for one tick
            await asyncio.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("\n\n🛑 Shutdown requested by user")

    except Exception as e:
        logger.error(f"\n\n💥 AGENT CRASHED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        logger.info("\n🧹 Cleaning up...")
        agent.running = False
        agent.visual_perception.stop_camera()
        await agent.audio_perception.stop()

        # Print summary
        event_logger.print_summary()

        logger.info("\n✅ Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
