# Engineering team roles and their permissions
ENGINEERING_ROLES = {
    "MECHANICAL": {
        "name": "Mechanical Engineering",
        "channels": ["mechanical", "cad", "manufacturing"],
        "default_interests": ["cad", "manufacturing", "mechanical-design", "thermal"],
        "can_access": ["mechanical", "cad", "manufacturing", "general"]
    },
    "ELECTRICAL": {
        "name": "Electrical Engineering",
        "channels": ["electrical", "battery", "power-electronics"],
        "default_interests": ["battery", "power-electronics", "electrical-design", "thermal"],
        "can_access": ["electrical", "battery", "power-electronics", "general"]
    },
    "SOFTWARE": {
        "name": "Software Engineering",
        "channels": ["software", "firmware", "controls"],
        "default_interests": ["firmware", "controls", "software-architecture", "testing"],
        "can_access": ["software", "firmware", "controls", "general"]
    },
    "SYSTEMS": {
        "name": "Systems Engineering",
        "channels": ["systems", "integration", "testing"],
        "default_interests": ["integration", "testing", "requirements", "validation"],
        "can_access": ["systems", "integration", "testing", "general"]
    },
    "PROJECT_MANAGER": {
        "name": "Project Management",
        "channels": ["project-management", "planning", "general"],
        "default_interests": ["planning", "milestones", "risks", "resources"],
        "can_access": ["*"]  # Can access all channels
    }
}

# Role hierarchy for permissions
ROLE_HIERARCHY = {
    "PROJECT_MANAGER": 4,  # Highest level
    "SYSTEMS": 3,
    "SOFTWARE": 2,
    "ELECTRICAL": 2,
    "MECHANICAL": 2,
    "DEFAULT": 1  # Base level
}

# Channel access levels
CHANNEL_ACCESS_LEVELS = {
    "general": 1,      # Everyone can access
    "mechanical": 2,   # Mechanical team and above
    "electrical": 2,   # Electrical team and above
    "software": 2,     # Software team and above
    "systems": 3,      # Systems team and above
    "management": 4    # Project managers only
} 