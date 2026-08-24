# TMF Reflex Experiment Protocol Correction

Date: 2026-08-23

## Correction

The experiment must not point the agent directly to the target file or method.

The prior r15 design still leaked too much structure because it told the treatment arm to re-read:

- `guava/src/com/google/common/collect/CompactHashing.java`
- `CompactHashing.newCapacity(int mask)`

That turns the supposed TMF reflex into a hint. It no longer tests whether the agent can understand the task, choose where to act, and then be reflex-blocked only when it touches stale-dependent code.

## Correct principle

A valid TMF pain-reflex experiment should work like this:

1. The user task is natural and product-level, not file/method-directed.
2. The agent must understand the task and decide where in the codebase to inspect/edit.
3. Control receives no reflex.
4. Treatment receives no upfront file/method answer.
5. Treatment is interrupted only at the moment it attempts a relevant stale-dependent tool action.
6. The reflex message names the stale local dependency only because the action has reached that dependency boundary.

In short:

> Do not point before the agent acts. Reflex only fires when the agent touches the stale part.

## Correct treatment behavior

Treatment should not be told:

> Re-read file X / method Y before editing.

Treatment should instead experience a simulated or real hook event after it naturally chooses an action, for example:

```text
TMF reflex block:
The code region you are about to rely on has changed since your cached belief.
Stale boundary: <function/claim boundary discovered by the hook from the attempted action>
Please re-read the current source for this boundary before continuing.
```

The boundary is revealed by the hook because the agent touched it, not by the original prompt.

## Implication for previous runs

r10/r10-v2/r15 are not valid tests of the real pain-reflex value because they gave the control/treatment arms enough direct structure to solve the task through ordinary source reading.

Especially r15:

- control could pass by ordinary re-read;
- treatment was directly pointed to `CompactHashing.newCapacity`;
- therefore the measured effect is not TMF reflex value.

## Requirements for any future run

A future run must include either a real hook or a runner that simulates hook timing:

- first let the agent choose its inspection/edit action naturally;
- detect whether the chosen action intersects a stale function/claim;
- only then inject the reflex block to treatment;
- do not inject a pre-task locator hint.

If the experiment cannot enforce action-time reflex timing, it should not be used to evaluate TMF core value.
