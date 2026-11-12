"""Per-event roles and what they may see (view) or change (edit)."""

from functools import wraps

from django.core.exceptions import PermissionDenied

VIEW, EDIT = "view", "edit"

#: Areas of the app. Every organiser view belongs to one.
AREAS = ["accreditation", "scan", "artists", "crew", "setup", "settings"]

MANAGER, ACCREDITATION, ARTISTS, CREW, CHECKIN, VIEWER = (
    "manager",
    "accreditation",
    "artists",
    "crew",
    "checkin",
    "viewer",
)

ROLES = {
    MANAGER: ("Manager", "Everything for this event, including settings, setup and the team."),
    ACCREDITATION: ("Accreditation", "People, approvals, companies and check-in."),
    ARTISTS: ("Artist liaison", "Artists, timetable, transport and hotels."),
    CREW: ("Crew coordinator", "Shifts, roster, volunteers and teams."),
    CHECKIN: ("Check-in staff", "Only the check-in scanner."),
    VIEWER: ("Viewer", "Read-only access to everything."),
}

CAPABILITIES = {
    MANAGER: {area: EDIT for area in AREAS},
    ACCREDITATION: {
        "accreditation": EDIT,
        "scan": EDIT,
        "artists": VIEW,
        "crew": VIEW,
        "setup": VIEW,
    },
    ARTISTS: {"artists": EDIT, "accreditation": VIEW, "setup": VIEW},
    CREW: {"crew": EDIT, "accreditation": VIEW, "setup": VIEW},
    CHECKIN: {"scan": EDIT},
    VIEWER: {"accreditation": VIEW, "artists": VIEW, "crew": VIEW, "setup": VIEW},
}


class Access:
    """What one user may do in one event."""

    def __init__(self, user, event):
        self.user = user
        self.event = event
        self.role = None
        if user.is_superuser:
            self.levels = {area: EDIT for area in AREAS}
            self.role_label = "Administrator"
            return
        from .models import Membership

        membership = Membership.objects.filter(user=user, event=event).first()
        self.role = membership.role if membership else None
        self.levels = dict(CAPABILITIES.get(self.role, {}))
        self.role_label = ROLES[self.role][0] if self.role else ""

    @property
    def is_member(self):
        return self.user.is_superuser or self.role is not None

    def can(self, area, edit=False):
        level = self.levels.get(area)
        return level == EDIT if edit else level in (VIEW, EDIT)

    @property
    def only_scans(self):
        return set(self.levels) == {"scan"}

    def flags(self):
        """For templates: {"accreditation": True, "edit_accreditation": False, …}."""
        flags = {}
        for area in AREAS:
            flags[area] = self.can(area)
            flags[f"edit_{area}"] = self.can(area, edit=True)
        return flags


def event_view(area=None):
    """Load the event from `slug` and check access before running the view.

    GET/HEAD need view rights on `area`, any other method needs edit rights.
    `area=None` only requires being a member of the event.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(request, slug, *args, **kwargs):
            from .helpers import get_event

            event = get_event(slug)
            access = Access(request.user, event)
            if not access.is_member:
                raise PermissionDenied("You don't have access to this event.")
            if area is not None:
                edit = request.method not in ("GET", "HEAD")
                if not access.can(area, edit=edit):
                    raise PermissionDenied(
                        "Your role doesn't allow this." if edit else "Your role can't open this page."
                    )
            request.event = event
            request.access = access
            request.area = area
            return view(request, slug, *args, **kwargs)

        wrapper.event_area = area
        return wrapper

    return decorator


def can_create_events(user):
    return user.is_superuser or user.is_staff
