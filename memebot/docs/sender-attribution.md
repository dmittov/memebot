# Sender Attribution for Forwarded Messages

## Feature

When users forward a message from a channel to the bot, the bot now shows who sent it rather than the original channel.

## Behavior

- **Forwarded messages**: Use `copy_message()` with attribution caption
  - Shows: "sent by @username" or "sent by First Last"
  - Preserves existing captions by appending attribution

- **Regular messages**: Use `forward_message()` as before
  - No attribution added
  - Standard Telegram forward behavior

## Example

User @jdoe forwards from "La Qeque" channel:
- Before: "Forwarded from: La Qeque"
- After: "sent by @jdoe" (in caption)

## Implementation

See `memebot/censor.py`:
- `build_sender_attribution()` - Creates attribution text
- `build_caption_with_attribution()` - Merges with existing caption
- `CensorSubscriber.check()` - Routes forwarded vs regular messages
