"""Brute-force protection for approver login.

Approvers are the human check on risky actions, so their passwords must not be
guessable at full speed. Every attempt, successful or not, counts against both
the username and the client address, using the same Redis limiter as agents.
"""

from dataclasses import dataclass

from redis import RedisError

from app.ratelimit import Limit, RateLimiter

LOGIN_LIMITS = (Limit(max_requests=10, window_seconds=300),)


@dataclass(frozen=True)
class LoginThrottle:
    allowed: bool
    retry_after_seconds: int = 0
    # Redis was unreachable: refuse the login rather than allow unlimited guessing (ADR-006).
    unavailable: bool = False


async def check_login_attempt(limiter: RateLimiter, username: str, client_ip: str | None) -> LoginThrottle:
    subjects = [f"login-user:{username.strip().lower()}"]
    if client_ip:
        subjects.append(f"login-ip:{client_ip}")
    try:
        for subject in subjects:
            result = await limiter.hit_subject(subject, LOGIN_LIMITS)
            if not result.allowed:
                return LoginThrottle(allowed=False, retry_after_seconds=max(1, round(result.retry_after_seconds)))
    except RedisError:
        return LoginThrottle(allowed=False, unavailable=True)
    return LoginThrottle(allowed=True)
