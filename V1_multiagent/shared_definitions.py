from enum import Enum, auto

class TutorStage(Enum):
    """Enum defining the possible stages of the tutor interaction."""
    PRE_DIFFERENTIAL = auto()  # Before the student has provided a differential diagnosis
    POST_DIFFERENTIAL = auto()  # After the student has provided a differential diagnosis
    KNOWLEDGE_ASSESSMENT = auto()  # During the knowledge assessment phase 