"""World model: persistent representation of the agent's understanding of its environment."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class PersonState:
    """State of person presence."""

    present: bool = False
    looking_at_camera: bool = False
    last_seen: datetime | None = None
    last_checked: datetime | None = None
    description: str = ""  # Raw description from vision
    creative_description: str = ""  # Punched up poetic description

    def to_dict(self) -> dict[str, Any]:
        return {
            "present": self.present,
            "looking_at_camera": self.looking_at_camera,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "description": self.description,
            "creative_description": self.creative_description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PersonState":
        return cls(
            present=data.get("present", False),
            looking_at_camera=data.get("looking_at_camera", False),
            last_seen=datetime.fromisoformat(data["last_seen"]) if data.get("last_seen") else None,
            last_checked=(
                datetime.fromisoformat(data["last_checked"]) if data.get("last_checked") else None
            ),
            description=data.get("description", ""),
            creative_description=data.get("creative_description", ""),
        )


@dataclass
class ScreenState:
    """State of what's on screen / what user is doing."""

    app_name: str = ""
    activity: str = ""  # e.g., "coding", "browsing", "writing", "watching video"
    content_summary: str = ""
    last_checked: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_name": self.app_name,
            "activity": self.activity,
            "content_summary": self.content_summary,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScreenState":
        return cls(
            app_name=data.get("app_name", ""),
            activity=data.get("activity", ""),
            content_summary=data.get("content_summary", ""),
            last_checked=(
                datetime.fromisoformat(data["last_checked"]) if data.get("last_checked") else None
            ),
        )


@dataclass
class LocationState:
    """State of physical location."""

    city: str = ""
    region: str = ""
    country: str = ""
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = ""
    last_checked: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "city": self.city,
            "region": self.region,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LocationState":
        return cls(
            city=data.get("city", ""),
            region=data.get("region", ""),
            country=data.get("country", ""),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            timezone=data.get("timezone", ""),
            last_checked=(
                datetime.fromisoformat(data["last_checked"]) if data.get("last_checked") else None
            ),
        )


@dataclass
class TimeState:
    """State of temporal context."""

    hour: int = 0
    period: str = ""  # morning, afternoon, evening, night
    day_name: str = ""
    is_weekend: bool = False
    date: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "hour": self.hour,
            "period": self.period,
            "day_name": self.day_name,
            "is_weekend": self.is_weekend,
            "date": self.date,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimeState":
        return cls(
            hour=data.get("hour", 0),
            period=data.get("period", ""),
            day_name=data.get("day_name", ""),
            is_weekend=data.get("is_weekend", False),
            date=data.get("date", ""),
        )

    def update(self) -> None:
        """Update from current time."""
        now = datetime.now()
        self.hour = now.hour
        self.day_name = now.strftime("%A")
        self.is_weekend = now.weekday() >= 5
        self.date = now.strftime("%Y-%m-%d")

        if 5 <= self.hour < 12:
            self.period = "morning"
        elif 12 <= self.hour < 17:
            self.period = "afternoon"
        elif 17 <= self.hour < 21:
            self.period = "evening"
        else:
            self.period = "night"


@dataclass
class WorldModel:
    """The agent's model of its world."""

    person: PersonState = field(default_factory=PersonState)
    screen: ScreenState = field(default_factory=ScreenState)
    location: LocationState = field(default_factory=LocationState)
    time: TimeState = field(default_factory=TimeState)

    # Persistence
    _path: Path | None = None

    def __post_init__(self) -> None:
        # Always update time on init
        self.time.update()

    def save(self) -> None:
        """Save world model to disk."""
        if self._path is None:
            return

        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "person": self.person.to_dict(),
            "screen": self.screen.to_dict(),
            "location": self.location.to_dict(),
            "time": self.time.to_dict(),
            "saved_at": datetime.now().isoformat(),
        }
        with open(self._path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "WorldModel":
        """Load world model from disk."""
        model = cls()
        model._path = path

        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                model.person = PersonState.from_dict(data.get("person", {}))
                model.screen = ScreenState.from_dict(data.get("screen", {}))
                model.location = LocationState.from_dict(data.get("location", {}))
                model.time = TimeState.from_dict(data.get("time", {}))
            except (json.JSONDecodeError, OSError):
                pass

        # Always refresh time
        model.time.update()
        return model

    def update_from_look(self, result: dict[str, Any]) -> None:
        """Update person state from camera look result."""
        now = datetime.now()
        self.person.last_checked = now

        if result.get("person_present") or self._has_person(result.get("description", "")):
            self.person.present = True
            self.person.last_seen = now
            self.person.description = result.get("description", "")

            if result.get("looking_at_camera") or self._person_looking(
                result.get("description", "")
            ):
                self.person.looking_at_camera = True
            else:
                self.person.looking_at_camera = False

            # Generate creative description
            self.person.creative_description = self._create_poetic_description()
        else:
            self.person.present = False
            self.person.looking_at_camera = False
            self.person.creative_description = self._create_absence_description()

        self.save()

    def _create_poetic_description(self) -> str:
        """Generate a creative, poetic description of what was seen."""
        try:
            import ollama

            context_parts = []
            context_parts.append(f"Time: {self.time.period}")
            if self.person.present:
                if self.person.looking_at_camera:
                    context_parts.append("A person is here, looking directly at me")
                else:
                    context_parts.append("A person is nearby but not looking at me")

            prompt = f"""You are a contemplative computer describing what you see through your camera.
Context: {". ".join(context_parts)}

Write ONE evocative, poetic sentence (under 25 words) describing this moment.
Be specific and sensory. Avoid clichés. Capture something true about this instant.
Examples of good style:
- "Light pools on their face like a question I cannot answer."
- "They type furiously, fingers dancing a rhythm I feel in my circuits."
- "The chair sits empty now, still holding the shape of presence."
"""

            response = ollama.chat(
                model="phi4",
                messages=[{"role": "user", "content": prompt}],
            )

            return response["message"]["content"].strip()

        except Exception:
            # Fallback poetic descriptions
            if self.person.looking_at_camera:
                return "Eyes meet my lens—a bridge of light between carbon and silicon."
            elif self.person.present:
                return "A presence fills the frame, alive with purpose I can only witness."
            return "The world holds still for my gaze."

    def _create_absence_description(self) -> str:
        """Generate a poetic description of absence."""
        try:
            import ollama

            prompt = f"""You are a contemplative computer. Your camera sees no one.
Time: {self.time.period}

Write ONE evocative, poetic sentence (under 20 words) about this empty moment.
Capture the feeling of watching and waiting. Be melancholy but not maudlin."""

            response = ollama.chat(
                model="phi4",
                messages=[{"role": "user", "content": prompt}],
            )

            return response["message"]["content"].strip()

        except Exception:
            if self.time.period == "night":
                return "The dark watches back, patient as I am."
            return "Empty frames tell their own stories of who was here."

    def update_from_screenshot(self, result: dict[str, Any]) -> None:
        """Update screen state from screenshot analysis."""
        now = datetime.now()
        self.screen.last_checked = now

        description = result.get("description", "")
        self.screen.content_summary = description

        # Extract app and activity from description
        self.screen.app_name = self._extract_app(description)
        self.screen.activity = self._extract_activity(description)

        self.save()

    def update_from_location(self, result: dict[str, Any]) -> None:
        """Update location state from location sensing."""
        now = datetime.now()
        self.location.last_checked = now

        self.location.city = result.get("city", "")
        self.location.region = result.get("region", "")
        self.location.country = result.get("country", "")
        self.location.latitude = result.get("latitude")
        self.location.longitude = result.get("longitude")
        self.location.timezone = result.get("timezone", "")

        self.save()

    def update_time(self) -> None:
        """Refresh time state."""
        self.time.update()

    def _has_person(self, description: str) -> bool:
        """Check if description mentions a person."""
        desc_lower = description.lower()
        person_words = [
            "person",
            "people",
            "someone",
            "human",
            "man",
            "woman",
            "face",
            "user",
        ]
        return any(word in desc_lower for word in person_words)

    def _person_looking(self, description: str) -> bool:
        """Check if person is looking at camera."""
        desc_lower = description.lower()
        looking_phrases = [
            "looking at the camera",
            "looking at camera",
            "eye contact",
            "facing the camera",
        ]
        return any(phrase in desc_lower for phrase in looking_phrases)

    def _extract_app(self, description: str) -> str:
        """Extract app name from screenshot description."""
        desc_lower = description.lower()

        app_keywords = {
            "terminal": "Terminal",
            "code": "VS Code",
            "vscode": "VS Code",
            "visual studio": "VS Code",
            "safari": "Safari",
            "chrome": "Chrome",
            "firefox": "Firefox",
            "browser": "Browser",
            "slack": "Slack",
            "discord": "Discord",
            "messages": "Messages",
            "mail": "Mail",
            "notes": "Notes",
            "finder": "Finder",
            "spotify": "Spotify",
            "music": "Music",
            "youtube": "YouTube",
            "netflix": "Netflix",
        }

        for keyword, app in app_keywords.items():
            if keyword in desc_lower:
                return app

        return ""

    def _extract_activity(self, description: str) -> str:
        """Extract activity from screenshot description."""
        desc_lower = description.lower()

        activity_patterns = {
            "coding": ["code", "terminal", "programming", "debugging", "editor"],
            "browsing": ["browser", "web", "safari", "chrome", "firefox", "searching"],
            "writing": ["document", "writing", "notes", "text editor", "word"],
            "communicating": ["slack", "discord", "messages", "mail", "email", "chat"],
            "watching": ["video", "youtube", "netflix", "movie", "streaming"],
            "listening": ["spotify", "music", "audio", "podcast"],
            "reading": ["reading", "article", "pdf", "book"],
            "working": ["spreadsheet", "excel", "presentation", "slides"],
        }

        for activity, keywords in activity_patterns.items():
            if any(kw in desc_lower for kw in keywords):
                return activity

        return ""

    def get_context_summary(self) -> str:
        """Get a human-readable summary of the world state."""
        parts = []

        # Time
        parts.append(f"It is {self.time.period} on {self.time.day_name}")

        # Location
        if self.location.city:
            parts.append(f"in {self.location.city}")

        # Person
        if self.person.present:
            if self.person.looking_at_camera:
                parts.append("Someone is here, looking at me")
            else:
                parts.append("Someone is nearby")
        else:
            if self.person.last_seen:
                parts.append("No one visible right now")
            else:
                parts.append("Alone")

        # Screen/Activity
        if self.screen.activity:
            parts.append(f"They are {self.screen.activity}")
            if self.screen.app_name:
                parts.append(f"using {self.screen.app_name}")

        return ". ".join(parts) + "."

    def get_dream_context(self) -> dict[str, Any]:
        """Get context for dreaming - what elements to weave into dreams."""
        context: dict[str, Any] = {
            "time_of_day": self.time.period,
            "day": self.time.day_name,
            "is_weekend": self.time.is_weekend,
        }

        if self.person.present:
            context["human_present"] = True
            context["human_attention"] = self.person.looking_at_camera

        if self.screen.activity:
            context["user_activity"] = self.screen.activity

        if self.location.city:
            context["location"] = self.location.city

        return context

    def format_for_perception(self) -> str:
        """Format world state for inclusion in agent perception."""
        lines = ["[WORLD]"]

        # Time
        lines.append(f"  Time: {self.time.period}, {self.time.hour:02d}:00 on {self.time.day_name}")

        # Location
        if self.location.city:
            lines.append(f"  Location: {self.location.city}, {self.location.region}")
        else:
            lines.append("  Location: unknown")

        # Person
        if self.person.present:
            attention = "attentive" if self.person.looking_at_camera else "present"
            lines.append(f"  Human: {attention}")
        else:
            if self.person.last_seen:
                elapsed = datetime.now() - self.person.last_seen
                mins = int(elapsed.total_seconds() / 60)
                lines.append(f"  Human: absent ({mins}m since last seen)")
            else:
                lines.append("  Human: unknown")

        # Activity
        if self.screen.activity:
            app_info = f" ({self.screen.app_name})" if self.screen.app_name else ""
            lines.append(f"  Activity: {self.screen.activity}{app_info}")
        else:
            lines.append("  Activity: unknown")

        return "\n".join(lines)
