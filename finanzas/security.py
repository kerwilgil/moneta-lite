"""Security helpers shared by authentication views and signals."""

import hashlib
import ipaddress
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone


def client_ip(request):
    """Resolve a client address only through explicitly trusted proxy ranges."""
    remote_value = request.META.get("REMOTE_ADDR", "")
    try:
        remote_ip = ipaddress.ip_address(remote_value)
    except ValueError:
        return "unknown"

    trusted_networks = []
    for value in getattr(settings, "MONETA_TRUSTED_PROXY_CIDRS", []):
        try:
            trusted_networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            continue

    trust_forwarded = getattr(settings, "MONETA_TRUST_X_FORWARDED_FOR", False)
    peer_is_trusted = any(remote_ip in network for network in trusted_networks)
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if not (trust_forwarded and peer_is_trusted and forwarded):
        return remote_ip.compressed

    try:
        chain = [ipaddress.ip_address(item.strip()) for item in forwarded.split(",") if item.strip()]
    except ValueError:
        return remote_ip.compressed
    chain.append(remote_ip)

    while chain and any(chain[-1] in network for network in trusted_networks):
        chain.pop()
    return (chain[-1] if chain else remote_ip).compressed


def _network_identity(ip_value):
    """Coarsen an IP before hashing so one-subnet rotation does not bypass throttling."""
    try:
        address = ipaddress.ip_address(ip_value)
    except ValueError:
        return "unknown"
    prefix = 24 if address.version == 4 else 64
    return ipaddress.ip_network(f"{address}/{prefix}", strict=False).with_prefixlen


def _digest(value):
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def throttle_keys(request, identity):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    username_field = User.USERNAME_FIELD
    normalized_identity = (identity or "").strip()
    known_identity = (
        User.objects.filter(**{f"{username_field}__iexact": normalized_identity})
        .values_list(username_field, flat=True)
        .first()
    )
    return (
        _digest(_network_identity(client_ip(request))),
        _digest(str(known_identity).casefold() if known_identity else "unknown-account"),
    )


def _increment_throttle(throttle):
    now = timezone.now()
    if throttle.locked_until and throttle.locked_until <= now:
        throttle.attempts = 0
        throttle.locked_until = None
    throttle.attempts += 1
    if throttle.attempts >= getattr(settings, "MONETA_LOGIN_MAX_ATTEMPTS", 10):
        throttle.attempts = 0
        throttle.locked_until = now + timedelta(
            seconds=getattr(settings, "MONETA_LOGIN_LOCKOUT_SECONDS", 900)
        )
    throttle.save(update_fields=["attempts", "locked_until", "updated_at"])


def record_login_failure(request, identity):
    """Increment one account+network throttle under a database row lock."""
    from .models import LoginThrottle

    network_hash, identity_hash = throttle_keys(request, identity)
    try:
        with transaction.atomic():
            throttle, _ = LoginThrottle.objects.select_for_update().get_or_create(
                network_hash=network_hash,
                identity_hash=identity_hash,
            )
            _increment_throttle(throttle)
    except IntegrityError:
        # A concurrent first failure may create the unique row first.
        with transaction.atomic():
            throttle = LoginThrottle.objects.select_for_update().get(
                network_hash=network_hash,
                identity_hash=identity_hash,
            )
            _increment_throttle(throttle)


def is_login_locked(request, identity):
    from .models import LoginThrottle

    network_hash, identity_hash = throttle_keys(request, identity)
    throttle = LoginThrottle.objects.filter(
        network_hash=network_hash,
        identity_hash=identity_hash,
    ).first()
    return bool(throttle and throttle.locked_until and throttle.locked_until > timezone.now())


def clear_login_failures(request, identity):
    from .models import LoginThrottle

    network_hash, identity_hash = throttle_keys(request, identity)
    LoginThrottle.objects.filter(
        network_hash=network_hash,
        identity_hash=identity_hash,
    ).delete()
