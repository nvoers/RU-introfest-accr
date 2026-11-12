"""Managing who works on an event (the Team page) and inviting new organisers."""

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from django.conf import settings

from .helpers import render_event
from .models import Membership, log
from .permissions import MANAGER, ROLES, event_view

ROLE_CHOICES = [(key, label) for key, (label, _) in ROLES.items()]


class InviteForm(forms.Form):
    email = forms.EmailField(label="E-mail")
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    role = forms.ChoiceField(choices=ROLE_CHOICES, initial="accreditation")


def set_password_link(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    path = reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token})
    return f"{settings.SITE_URL}{path}"


def send_invite(user, event, inviter):
    who = inviter.get_full_name() or inviter.get_username()
    if user.has_usable_password():
        action = f"Sign in with your existing account: {settings.SITE_URL}{reverse('login')}"
    else:
        action = f"Choose a password to activate your account:\n{set_password_link(user)}"
    send_mail(
        subject=f"You've been added to {event.name}",
        message=(
            f"Hi {user.first_name or user.email},\n\n{who} added you to the team of "
            f"{event.name}.\n\n{action}\n\nYour login is {user.email}."
        ),
        from_email=None,
        recipient_list=[user.email],
    )


@event_view("settings")
def team(request, slug):
    event = request.event
    User = get_user_model()
    form = InviteForm(request.POST or None, prefix="f-new") if request.POST.get("action") == "invite" else InviteForm(prefix="f-new")
    open_dialog = None

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "invite":
            if form.is_valid():
                data = form.cleaned_data
                email = data["email"].lower()
                user = User.objects.filter(email__iexact=email).first()
                created = user is None
                if created:
                    user = User(username=email, email=email,
                                first_name=data["first_name"], last_name=data["last_name"])
                    user.set_unusable_password()
                    user.save()
                membership, new = Membership.objects.update_or_create(
                    user=user, event=event, defaults={"role": data["role"], "invited_by": request.user}
                )
                send_invite(user, event, request.user)
                log(event, f"{'Invited' if new else 'Updated'} {email} as {membership.role_label}", request.user)
                messages.success(
                    request,
                    f"{email} {'invited' if new else 'updated'} as {membership.role_label}"
                    + (" – they'll get an e-mail to set their password." if created else "."),
                )
                return redirect("team", event.slug)
            open_dialog = "dlg-new"
        else:
            membership = get_object_or_404(event.memberships.select_related("user"), pk=request.POST.get("item"))
            managers = event.memberships.filter(role=MANAGER)
            is_last_manager = membership.role == MANAGER and managers.count() == 1
            if action == "role" and request.POST.get("role") in ROLES:
                if is_last_manager and request.POST["role"] != MANAGER:
                    messages.error(request, "An event needs at least one manager.")
                else:
                    membership.role = request.POST["role"]
                    membership.save(update_fields=["role"])
                    log(event, f"{membership.user.email or membership.user} is now {membership.role_label}", request.user)
                    messages.success(request, f"Role changed to {membership.role_label}.")
            elif action == "remove":
                if is_last_manager:
                    messages.error(request, "An event needs at least one manager.")
                else:
                    membership.delete()
                    log(event, f"Removed {membership.user.email or membership.user} from the team", request.user)
                    messages.success(request, "Removed from the team.")
            elif action == "resend":
                send_invite(membership.user, event, request.user)
                messages.success(request, f"Invite sent again to {membership.user.email}.")
        return redirect("team", event.slug)

    return render_event(
        request,
        event,
        "core/team.html",
        {
            "members": event.memberships.select_related("user", "invited_by"),
            "admins": User.objects.filter(is_superuser=True, is_active=True),
            "new_form": form,
            "roles": ROLES,
            "open_dialog": open_dialog,
        },
        section="team",
    )
