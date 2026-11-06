# Ordinary Property build: offline slice

Status: implemented and checked offline; native/live proof open.

Saved native `PropertyBlock` calls `BuyProperty:InvokeServer(propId,
optionalSlot)`; its normal Build button omits the slot. The displayed
price rounds `baseCost * 1.18^owned`, then applies capped Territory
build discount and rounds again. The UI checks level, vacant capacity
and cash. This slice will only propose a nondestructive Build with no
slot argument. It will require complete replicated counts, a current
catalog, same-snapshot capacity/discount proof and separate purchase
limits; uncertain cash remains reserved. A successful reply alone is
insufficient: a newer same-account Sync must increase the exact
selected property's owned count by one.

Test quote rounding, selection policies, cap/reserve, malformed proof,
and exact evidence through the fake broker. Deletion, moves and
replacement remain outside this slice. Native adapter and live server
outcome remain open.
