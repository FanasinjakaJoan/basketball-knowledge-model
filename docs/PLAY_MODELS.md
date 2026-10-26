# Play models

Three plays are modelled end to end. Each one is a **graph**, not a list: steps are
nodes, ordering is `precedes`, and the reads are `Decision` nodes that branch on what
the defence does. Every step carries its actor, its action type, the zones it moves
between, the archetypes it requires and the rules that constrain it.

```bash
python -m basketball_kg.cli ask "walk me through the pick and roll"
python -m basketball_kg.cli export -f dot --focus play:pick-and-roll --out pnr.dot
dot -Tpng pnr.dot -o pnr.png        # requires graphviz
```

---

## 1. Pick and Roll — `play:pick-and-roll`

**Formation:** 4-out-1-in (equally playable from 5-out) · **19 steps, 1 decision point**
**Needs:** pick-and-roll initiator + rim-running big · **Produces:** rim attempt, lob
dunk, corner three, above-break three, mismatch, foul drawn

The spine is `spacing → align angle → screen → use screen → (weak-side lift, roll) →
◇ read the coverage → branch`. The whole point of the action is the branch: the coverage
the defence chooses *is* the input.

| order | label | actionType | actor | from | to | branch |
|---|---|---|---|---|---|---|
| 1 | Establish spacing: 4-out-1-in, both corners filled | Establish spacing | Off-Ball Mover |  | Frontcourt |  |
| 2 | Set up the screen angle | Set up the screen angle | Ball Handler | Top of Key Three | Top of Key Three |  |
| 3 | Set the on-ball screen | Set an on-ball screen (ball screen) | Screener | High Post (Free-Throw Line) | Top of Key Three |  |
| 4 | Use the screen shoulder-to-hip | Use the screen | Ball Handler | Top of Key Three | High Post (Free-Throw Line) |  |
| 5 | Roll to the rim | Roll to the rim | Roll Man | Top of Key Three | Restricted Area (Rim) |  |
| 6 | Weak side lifts and relocates | Relocate | Spot-Up Shooter | Right Corner Three | Right Wing Three (Above the Break) |  |
| 7 | DECISION — Read the coverage | read |  |  |  |  |
| 8 | Short roll against the blitz | Short roll (roll to the elbow) | Roll Man | Top of Key Three | Left Elbow | blitz |
| 8 | Slip the screen against a switch | Slip the screen | Screener | Top of Key Three | Restricted Area (Rim) | switch |
| 8 | Post the mismatch after a switch | Post up | Roll Man |  | Left Low Post (Block) | switch |
| 8 | Step-back isolation against a switch | Step-back three | Ball Handler |  | Left Wing Three (Above the Break) | switch |
| 8 | Reject the screen against ICE | Reject the screen | Ball Handler | Top of Key Three | High Post (Free-Throw Line) | ice |
| 8 | Pull up against drop coverage | Pull-up jump shot | Ball Handler |  | Top of Key Three | drop |
| 8 | Pop instead of rolling against drop coverage | Pop to the perimeter | Pop Man | Top of Key Three | Right Wing Three (Above the Break) | drop |
| 8 | Snake the screen against drop coverage | Snake the ball screen | Ball Handler | High Post (Free-Throw Line) | Paint (Lane) | drop |
| 9 | Skip the ball out of the trap | Skip pass | Hub | Left Elbow | Right Wing Three (Above the Break) | blitz |
| 9 | Lob finish | Lob finish | Roll Man |  | Restricted Area (Rim) | switch |
| 9 | Reverse the ball to the weak side | Ball reversal | Connector | High Post (Free-Throw Line) | Right Wing Three (Above the Break) | ice |
| 9 | Deliver the pocket pass or the lob | Pocket pass | Ball Handler | High Post (Free-Throw Line) | Paint (Lane) | default |
| 10 | Catch and shoot | Catch-and-shoot | Spot-Up Shooter |  | Right Wing Three (Above the Break) | blitz |

### The read, coverage by coverage

Each branch is linked to the coverage it answers (`pnr:s7-pullup-vs-drop -answers-> coverage:drop`),
which is what makes "what beats drop coverage?" a traversal rather than a text search.

| Coverage | What it takes away | What the graph says to do |
|---|---|---|
| **Drop** | The rim and the roll | Pull up before the big's shadow; snake the screen to string him out; or pop instead of rolling to pull him out of the paint |
| **Blitz** | The ball handler's hands | Short roll to the elbow and play 4-on-3, then skip to the weak side before the second rotation |
| **Switch** | The pass out of the screen | Slip the screen before the switcher is set, post the mismatch before the scram arrives, or isolate with a step-back late in the clock |
| **ICE / Blue** | The middle and the pull-up | Reject the screen back to the middle, then reverse the ball: the second rotation is always late |
| **No help** | Nothing | Pocket pass or lob to the roller |

### Rules that bind the action

```bash
python -m basketball_kg.cli ask "what rules govern setting a screen?"
```

`rule:legal-screen` (stationary at contact) binds every screening action type;
`rule:offensive-three-seconds` keeps the roll man moving through the lane;
`rule:defensive-three-seconds` is why the defending big cannot simply camp there;
`rule:traveling-gather` bounds the gather into the pull-up; `rule:goaltending` bounds the lob.

### What the defence does to it

`counter:switch-vs-pnr`, `counter:blitz-vs-pnr`, `counter:ice-vs-pnr` — each names the
weakness it attacks and a rationale.

---

## 2. Motion Offence — `play:motion-offense`

**Formation:** 5-out · **11 steps, 1 decision point**
**Needs:** secondary creator + off-ball sharpshooter + 3-and-D wing

Motion is not a script, it is a rule set. The graph encodes the canonical sequence and
the rules live in `props.key`:

* pass and cut — after every pass the passer moves
* fill from the bottom — never leave two players in one spot
* backdoor a defender who overplays, basket-cut one who relaxes
* half-second decisions: catch, read, shoot–pass–drive
* one player per spot; the corners are always occupied

| order | label | actionType | actor | from | to | branch |
|---|---|---|---|---|---|---|
| 1 | Set the five spots | Establish spacing | Off-Ball Mover |  | Frontcourt |  |
| 2 | Pass the ball | Ball reversal | Connector | Top of Key Three | Left Wing Three (Above the Break) |  |
| 3 | Cut after the pass | Basket cut | Off-Ball Mover | Top of Key Three | Restricted Area (Rim) |  |
| 4 | Fill the vacant spot | Fill the vacant spot | Connector |  | Top of Key Three |  |
| 5 | DECISION — Read how the defender plays the cut | read |  |  |  |  |
| 6 | Finish the basket cut | Basket cut | Off-Ball Mover | Left Wing Three (Above the Break) | Restricted Area (Rim) | defender trails |
| 6 | Backdoor the overplay | Backdoor cut | Off-Ball Mover | Left Wing Three (Above the Break) | Restricted Area (Rim) | defender overplays |
| 6 | Relocate to an open spot | Relocate | Off-Ball Mover | Left Wing Three (Above the Break) | Left Corner Three | cut denied, defence set |
| 7 | Screen away from the ball | Down screen | Screener | Right Elbow | Right Corner Three |  |
| 8 | Screener re-screens or pops | Staggered screen | Screener |  | Right Elbow |  |
| 9 | Dribble hand-off or dribble-at | Dribble hand-off (DHO) | Connector | Right Wing Three (Above the Break) | Top of Key Three |  |
| 10 | Drive the closeout and kick it out | Kick-out pass | Connector | Top of Key Three | Left Corner Three |  |
| 11 | Crash the glass or retreat to safety | Crash the offensive glass | Rebounder / Boxer-Out |  | Paint (Lane) |  |

The single decision node branches on **how the defender plays the cut** — the whole
offence reduces to that one read. Answers: `counter:switch-vs-motion` (switch every
off-ball screen) and `counter:physicality-vs-motion` (deny the first pass, fill the
cutting lanes) — the latter constrained by `rule:freedom-of-movement`, and answered in
turn by `mot:s7-backdoor-cut`.

---

## 3. Zone 2-3 Defence — `play:zone-defense-2-3`

**Formation:** 2-3 shell · **5 area assignments, 8 movement steps, 5 counters**
**Needs:** rim protector + help-side roamer + perimeter stopper

### Area assignments

| label | heldBy | coversZones |
|---|---|---|
| Top-left guard | On-Ball Defender | High Post (Free-Throw Line), Top of Key Three, Left Wing Three (Above the Break) |
| Top-right guard | Perimeter Stopper | High Post (Free-Throw Line), Top of Key Three, Right Wing Three (Above the Break) |
| Bottom-left (forward) | Help Defender (Nail / Low Man) | Left Corner Three, Left Elbow, Left Low Post (Block), Left Short Corner |
| Bottom-middle (anchor) | Rim Protector | High Post (Free-Throw Line), Paint (Lane), Restricted Area (Rim) |
| Bottom-right (forward) | Help Defender (Nail / Low Man) | Right Corner Three, Right Elbow, Right Low Post (Block), Right Short Corner |

On the floor:

```console
$ python -m basketball_kg.cli court --scheme scheme:zone-2-3

|                      ............      [T3]    ............                      |
|           [W3<].......                                    .......  [W3>]         |
|            ... MW<                                              MW> .            |
|         ....                           [HP]                         ....         |
|      ....                 EL< ---------------------- EL>               ....      |
|    :      [SC<]           |  [LP<]     [PNT]    [LP>]|             [SC>]    :    |
|    :[C3<]                 |      :::   [RA] :::      |                   [C3>]   |
```

The **elbows are the seam**: they are the one spot two adjacent areas both claim, and
the bottom men only reach them when the ball is on their side.

### Movement rules

| order | label | actionType | actor | from | to |
|---|---|---|---|---|---|
| 1 | Set the shell | Establish spacing | Help Defender (Nail / Low Man) |  | Frontcourt |
| 2 | Top defenders match the ball | Contain the ball | On-Ball Defender | Top of Key Three | Left Wing Three (Above the Break) |
| 3 | Bottom three align to the ball | Rotate | Help Defender (Nail / Low Man) | Paint (Lane) | Left Short Corner |
| 4 | Touch the midline | Touch the midline | Help Defender (Nail / Low Man) |  | Paint (Lane) |
| 5 | Bump the cutter, then release him | Bump the cutter | Help Defender (Nail / Low Man) |  | Paint (Lane) |
| 6 | Rotate on the flight of the ball | Rotate | Help Defender (Nail / Low Man) | Left Short Corner | Right Short Corner |
| 7 | Answer the ball reversal | Closeout | Perimeter Stopper | Left Wing Three (Above the Break) | Right Wing Three (Above the Break) |
| 8 | Find a body and box out | Box out | Rebounder / Boxer-Out |  | Paint (Lane) |

`z23:s4-touch-midline` and `z23:s5-bump-cutter` are the two rules that make a zone a
zone — and both are bounded by rules: the midline by `rule:defensive-three-seconds`
(the weak-side man may not camp in the lane), the bump by `rule:freedom-of-movement`
(a bump is a momentary displacement, not a hold).

### Attacking it

```bash
python -m basketball_kg.cli ask "how do you attack a 2-3 zone?"
```

| label | vulnerability | exploits | effectiveness |
|---|---|---|---|
| Quick ball reversal against the 2-3 | A zone moves on the flight of the ball; two quick reversals beat the rotation | Left Short Corner, Left Wing Three, Right Wing Three | high |
| Occupy the high post against the 2-3 | The free-throw line is the geometric hole of the 2-3 shell | High Post (Free-Throw Line) | high |
| Crash the offensive glass against the 2-3 | Zone defenders are responsible for space, not for a body to box out | Paint (Lane), Restricted Area (Rim) | high |
| Overload one side of the 2-3 | A zone must allocate one defender per area; overloading breaks the allocation | Left Corner Three, Right Corner Three | high |
| Run before the 2-3 can set | A zone needs time and a dead ball to organise | Backcourt | high |

---

## Querying a play

```bash
# the whole action graph
python -m basketball_kg.cli query play_steps --play play:pick-and-roll

# one step in context
python -m basketball_kg.cli query sequence --action pnr:s10-shortroll-vs-blitz

# what personnel does it take?
python -m basketball_kg.cli query requirements --target play:motion-offense

# what does the rulebook say about it?
python -m basketball_kg.cli query rules --target play:pick-and-roll
```

In SPARQL (`queries/sparql/01-pick-and-roll-steps.rq`) the same question is:

```sparql
SELECT ?order ?step ?stepLabel ?actionType ?actor ?fromZone ?toZone ?next
WHERE {
  ?play bk:hasStep ?step .
  FILTER(?play = <https://w3id.org/basketball-kg/resource/play/pick-and-roll>)
  ?step skos:prefLabel ?stepLabel .
  OPTIONAL { ?step bk:order ?order }
  OPTIONAL { ?step bk:hasActionType ?actionType }
  OPTIONAL { ?step bk:actor ?actor }
  OPTIONAL { ?step bk:startsIn ?fromZone }
  OPTIONAL { ?step bk:endsIn ?toZone }
  OPTIONAL { SELECT ?step (GROUP_CONCAT(?nextLabel; SEPARATOR=", ") AS ?next)
             WHERE { ?step bk:precedes/skos:prefLabel ?nextLabel }
             GROUP BY ?step }
}
ORDER BY ?order
```
