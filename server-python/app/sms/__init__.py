"""SMS advisories sent by an agricultural technologist.

Two senders behind one interface (see senders.py):

  console          — writes the message to the server log and records it in
                     the outbox. No network, no SIM, no credits. This is the
                     default, so the feature demonstrates end to end with no
                     phone attached and still works if the handset is flat or
                     off the network mid-defense.

  android_gateway  — relays to "SMS Gateway for Android" running in Local
                     Server mode on a handset, which sends through that
                     phone's own SIM:
                         POST http://<phone>:8080/message
                         Basic auth
                         {"textMessage": {"text": ...}, "phoneNumbers": [...]}

Which one runs is a .env setting (SMS_PROVIDER), not a code change, so the
same build serves both the simulated and the live demo.
"""

from app.sms.senders import SendOutcome, get_sender, normalise_phone

__all__ = ["SendOutcome", "get_sender", "normalise_phone"]
