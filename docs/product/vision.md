# Product Vision and Customer Context

> Back to [README](../../README.md) · [Sprint 0](../../sprint0.md)

## Vision statement

**GetDrove gives UofM students a seat that's actually theirs.**

Getting to Fort Garry without a car means two buses and a transfer with no margin. If the first bus runs five minutes late the connection is gone and the next one is twenty minutes out. Worse, buses fill up before they reach the outer stops, so a student can be on time at the right stop and still watch a full bus drive past. Sometimes the next one is full too. There's no way to plan around it, because the schedule says a bus is coming and it's technically correct. The result is students building a forty-minute buffer into every morning, or showing up late anyway.

The alternative is driving, but a parking pass costs hundreds of dollars and the lots have a waitlist. So students without cars stay stuck with transit, while hundreds of students drive the same routes every morning alone, with three empty seats, paying for fuel and parking by themselves.

The seats exist. The coordination doesn't.

GetDrove closes that gap. Drivers post their commute the night before. The system works out their real driving route, shows the trip to students along it, and tells the driver how many extra minutes each rider would add. Riders get a confirmed seat, a pickup point, a live ETA, and a fair share of the cost based on how far they rode. Both sides are verified and rated, and nobody has to argue about gas money over text.

The goal is simple: a student should be able to take the 8:30 class knowing they'll get there.

## Customer

**UofM students who commute to the Fort Garry campus.**

A student with a 9:30 class in the suburbs leaves home at 7:45. Two buses, one transfer, no margin. If the first bus is five minutes late the connection is gone and the next one is twenty minutes out, so they're late, or they build a forty-minute buffer into every morning just in case.

Then there's the bus that arrives on time and doesn't stop. At peak hours on the routes feeding campus, buses fill before they reach the outer stops, and a full bus drives past. Being on time and at the right stop doesn't help; the student is simply not getting on. Sometimes the next one is full too. A student can do everything right and still lose half an hour standing in -35 with the wind off open fields, watching two buses go by.

The alternative is driving, but a parking pass costs hundreds of dollars and the lots have a waitlist. So students without cars stay stuck with transit, while hundreds of students with cars drive the same corridors every morning, alone, three empty seats, paying for fuel and parking by themselves.

Students already try to close this gap in Facebook groups and course chats, but there's no way to verify a stranger is a student, no way to know whether a pickup is actually on the driver's route, and no accountability when someone doesn't show.

GetDrove is for the students on both sides of that gap: the ones losing hours and getting passed by, and the ones already making the drive who'd take riders if it didn't cost them time.

## Primary users

**Student riders.** No car, or no parking pass. Currently losing one to three hours a day to transit, or paying rideshare fares they can't sustain. They need a ride reliable enough to plan a class schedule around, a seat that's actually theirs, and they need to know who they're getting in the car with.

**Student drivers.** They commute to Fort Garry on a regular schedule and want to offset fuel and parking. They'll take riders, but not if it means a fifteen-minute detour or someone who doesn't show up. They need control over who gets in their car and an honest answer to "what does this pickup actually cost me?"

Most students are both at different times, so driver and rider are roles on a single account.

## Secondary stakeholders

**UofM Parking Services.** Not involved, but affected. Fewer single-occupancy vehicles eases pressure on a lot system with a waitlist.

**People waiting on a student to get home.** Parents, partners, roommates. They're the reason trip sharing exists.

## Out of scope

Faculty and staff (non-students) and non-UofM riders are not users. GetDrove is student-to-student, Winnipeg to Fort Garry.

## How the features serve the vision

| Problem from the vision | Feature that addresses it |
|---|---|
| No way to verify a stranger is a student | [Accounts and verification](core-features.md#accounts-and-verification) |
| Students re-planning every night | [Trip posting](core-features.md#trip-posting) with recurring weekday trips |
| No way to know a pickup is on the driver's route | [Route matching](core-features.md#route-matching) by real road distance |
| Drivers won't accept long detours | [Requests and acceptance](core-features.md#requests-and-acceptance) with the detour cost shown |
| Uncertainty on the day | [Trip execution](core-features.md#trip-execution): pickup point, live ETA, reminders |
| Arguing about gas money over text | [Cost splitting and payment](core-features.md#cost-splitting-and-payment) by distance |
| No accountability when someone doesn't show | [Ratings and safety](core-features.md#ratings-and-safety) with no-show tracking |

See also: [Non-functional expectations](non-functional.md)
