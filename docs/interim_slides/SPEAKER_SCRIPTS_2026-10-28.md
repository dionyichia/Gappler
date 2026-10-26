# Interim presentation: speaker scripts, 28 Oct 2026

Copied word for word from docs/INTERIM_PRESENTATION_SLIDE_CONTENT_2026-10.md. The same text is in each slide's speaker notes in the .pptx.

Slot times sum to 19:20 plus 0:40 of handovers = 20:00. The scripts total about 3,170 words, which needs about 160 words a minute to fit.

## Slide 1: High-Readiness Mobile Manipulation via Gaze-Speech Interaction and Continuous Pre-Alignment

**Dion** | slot 0:20 | elapsed at end 0:20

Good afternoon. We are Dion, Sherman and Zongzhe. Our project is a mobile robot that fetches the specific object a person looked at and named, even when the robot cannot see that object at the start.

*Transition:* "Here is the situation we want the robot to handle."

## Slide 2: The user can see the object. The robot sees neither the user nor the object

**Dion** | slot 0:50 | elapsed at end 1:10

Picture a user wearing Meta's Aria glasses. They look at a box on a table and say 'pick up that box'. The robot is somewhere else in the room. It has never seen the user's view.

These three images show why that is hard. On the left is what the glasses see: the box from a metre or two away, front on. In the middle, the robot's base camera, at knee height. On the right, the wrist camera on the arm, looking down from twenty centimetres. Same object, but the images have almost nothing in common. Yet the robot has to find, and pick up, exactly the box the user looked at.

*Transition:* "Two published systems each solve half of this."

## Slide 3: Objective: join FAM-HRI's gaze and speech with HiCo-Nav's exploration and memory

**Dion** | slot 1:20 | elapsed at end 2:30

Our objective is a mobile manipulator that takes what the user says and where they look, explores a room it cannot see at the start, finds that object, drives to it and grasps it.

Two published systems each solve half of this. FAM-HRI uses the same Aria glasses: speech gives the object word, gaze picks which object, and an arm grasps it. But it assumes the object is already in front of the arm. We take its user side: speech, gaze and the grasp.

HiCo-Nav is a robot that explores an unseen room and builds a memory graph of every object it sees, each with a 3D position and an image feature. But you query it with a sentence, so it finds a class, any box, not the one you looked at. We take its pose estimation, its memory graph, its sentence reasoning and its exploration. We leave out its own motion planner and send goals to Nav2 instead. Its smarter way of choosing where to explore next is optional.

What we add is the join. The robot compares each object it finds with the one the user looked at, drives to the match, and checks it with the wrist camera before grasping.

*Transition:* "Here is the full behaviour we are building towards."

## Slide 4: The target system works in five phases, from speech and gaze to a grasp

**Zongzhe** | slot 1:15 | elapsed at end 3:50

The finished system works in five phases. First, the user speaks and looks. Speech gives us the word, gaze tells us which object, and we cut an image crop of it and turn it into a CLIP feature. Second, the robot explores. It maps the room and builds a memory of the objects it sees, each with a 3D position and an image feature. It looks for the user first, because the object is somewhere the user can see. Third, it compares what it sees with the user's target. A good match tells it to stop exploring. Fourth, it drives close and the camera on the arm confirms that this is the object the user meant. If not, it goes back to exploring. Fifth, it grasps.

Exploration is the core of the search. HiCo-Nav also has a smarter way to choose where to explore next. That part is optional and the first thing we cut if time runs short. Bringing the object back to the user is out of scope.

The badges show where each phase stands seven weeks in. The next eleven minutes go through them in order.

*Transition:* "Before the results, a word on where we started and how we work."

## Slide 5: We inherited code that did not run, so we built a test bench and a contract first

**Sherman** | slot 0:45 | elapsed at end 4:40

We did not start from a working system. The inherited code had no tests and no CI, and none of it ran from a fresh copy. One program homed the real arm within seconds, with no prompt. Navigation ran only from another user's workspace, and our copy did not build. There was no memory graph.

So we built foundations first. Dion took the glasses and the arm, I took the base and mapping, and Zongzhe the memory graph. A channel contract says who owns every message and frame, and a seven-level test bench runs on every pull request. We measure a baseline before replacing anything, and on the real robot we move one step at a time, with two people present.

*Transition:* "Phase one: turning a sentence and a glance into a target."

## Slide 6: Speech gives the word, gaze picks the object: right box in 60 of 61 recorded frames

**Dion** | slot 1:20 | elapsed at end 6:05

The user says 'find the box'. A speech detector waits for the sentence to finish, Whisper turns it into text, and a small language model pulls out the object word. Before this, the old pipeline produced thirty-one messages per phrase. Now it produces one.

Gaze runs at the same time. We keep the last twenty seconds of glasses images and gaze points, so we can go back to the moment the user was speaking. SAM 3, a segmentation model you prompt with a word, finds every box in that one frame. Then gaze votes. Each gaze sample in a one-second window votes for the mask it lands on, and the winner needs half the votes. We crop that mask with a small margin. That crop is what we send to the robot.

On a recording at 1.4 to 2.4 metres, this picked the right box in 60 of 61 frames. On a full replay, all four spoken words produced a crop.

The limit is gaze accuracy. The eye model is off by about five and a half degrees, roughly 15 centimetres at 1.5 metres. Here, at 1.5 metres, it landed on a stack of mats that SAM 3 also called a box. Keep that case in mind. It comes back on slide 12.

*Transition:* "That crop now has to be found by a robot that has never seen this view. Sherman will show how the robot knows where it is."

## Slide 7: The base builds a coloured 3D map that closes within 12 mm over a 26 m loop

**Sherman** | slot 1:35 | elapsed at end 7:45

Before the robot can remember where objects are, it needs to know where it is. We use FAST-LIVO2, the method the HiCo-Nav paper uses, from the University of Hong Kong. It fuses the LiDAR, its motion sensor and the colour camera into one pose, and paints a coloured 3D map.

Why 3D? 2D SLAM knows only where the base is on the floor and which way it faces. The memory graph places each object in 3D from the camera's pose, so an unmeasured tilt moves objects by centimetres. Nav2 still drives on a 2D grid built from this pose.

FAST-LIVO2 is published for ROS 1. We run a community ROS 2 port, and getting it to work was most of the effort. The strip along the bottom shows the steps. I proved it on the authors' own recording first, then on our sensors with every message checked. I found three defects that fail silently: no crash, just a wrong map. Each was found by reading the source and confirmed against a control run.

The result: I pushed the base by hand around a 26-metre loop. The path returns to its start within 12 millimetres, and the mid-route error is within about 7 centimetres, the limit of our reference. The pose now feeds Nav2's frame tree. Nav2 driving the base is the next test.

*Transition:* "A map is only useful to the arm and the memory if every camera's position on the robot is known. That is a calibration question, and there are several of them."

## Slide 8: Four camera relationships, four different states of calibration

**Sherman** | slot 1:10 | elapsed at end 8:55

There are four places where we need to know how one part of the robot sits relative to another.

The arm on the base is measured. We set the transform from the mount drawings and checked it on the robot. The base's own origin, on the floor under the drive axle, matches the vendor's manual.

The base camera relative to the LiDAR is measured but not calibrated. I designed and fitted the mount, measured to the camera's mounting hole, and took the rest from Intel's published camera dimensions. It sits flush on vertical aluminium extrusions, so it points straight by construction. What is left is a calibration against the LiDAR itself, because one degree of error moves a point by about seven pixels. The rig for that is planned.

The wrist camera relative to the arm is calibrated, so a grasp it sees becomes an arm goal.

The last one is different in kind. To use gaze to separate two identical objects, the robot needs the user's gaze ray in its own frame, which means locating the glasses relative to the robot. That is planned for January.

None of these blocks today's results, but each one blocks a specific later step.

*Transition:* "With poses and camera images from that drive, Zongzhe builds the robot's memory of the room."

## Slide 9: The memory graph turns a drive into objects with a position and an image feature

**Zongzhe** | slot 1:20 | elapsed at end 10:20

The memory graph is HiCo-Nav's idea. As the robot moves, it keeps a photo now and then, finds the objects in it, and stores each object with its position in 3D and a CLIP image feature. CLIP is a model that turns an image into a vector, so that similar-looking things get similar vectors. The photos are kept too, linked to the objects they show. That link is the 'graph'.

HiCo-Nav published code, but with no licence, so I read it and wrote a fresh implementation as fourteen separate stages, each with its own tests. Reading it also turned up nine problems, such as a language-model call with no timeout, which we fixed or avoided.

Here is the graph built from Sherman's hand-pushed drive. Two choices keep it fast. A photo is kept only after the robot moves a metre or turns 45 degrees, so 29 of 3,536 frames go to segmentation, which saves over 99 % of that time. And all thirty object classes go through SAM 3 in one batch, 5.7 times faster than one at a time.

It is built offline from a recording. Building it live while the robot explores is next (T7.2, T7.5).

*Transition:* "The hardest part of building it is deciding when two sightings are the same object."

## Slide 10: A 10 cm merge radius cut duplicates from 8 to 3 with no false merges

**Zongzhe** | slot 1:00 | elapsed at end 11:20

The robot sees the same chair from many places. Each sighting must merge into one object, and two chairs side by side must stay two.

To measure that, I made an answer key by hand: sixteen real objects marked on the LiDAR map, without using any of the code being tested. Then I swept the settings.

The lever is the match radius, how close two sightings' points must be. With our sparse LiDAR depth, two views of one object land 4 to 9 centimetres apart, so upstream's 2.5 centimetres split objects. At 10 centimetres duplicates fall from 8 to 3 with no false merges. On a second drive, 2 to 1. At 15, a chair merges into the desk next to it, so we chose 10.

Why not just merge things that look alike? Because look-alikes are exactly the problem. CLIP scores two chairs of the same model at 0.81 to 0.85, close to the same chair at 0.93. Merging on appearance removes every duplicate by merging nearly everything. That is also why the class alone cannot find the user's object.

*Transition:* "Once the objects are in the graph, the robot has to find the right one from a sentence."

## Slide 11: A sentence becomes a ranked list of objects with 3D positions

**Zongzhe** | slot 0:50 | elapsed at end 12:10

To search the graph, the robot first turns the sentence into classes. A small language model, running locally, returns the target class and some related ones. 'Find the chair' gives chair, plus table and desk, because chairs are usually near them. The 1.5 billion parameter model got 20 of 22 test instructions right and answers in about a third of a second.

Then every object is scored by comparing its stored image feature with the sentence, using CLIP again. Target classes rank first, related ones after. Each hit comes with a 3D position and the best photo of it, and a wrong hit can be rejected so the robot tries the next one.

The ranking has been tested on stand-in data and a few photos. Running the full query on the recorded drive, checked against the answer key, is the next milestone, in the next two weeks.

Today the query is a sentence. In the full system, the robot matches each object against the gaze crop from slide 6, and a good match tells it to stop exploring and go to the user's chair, not just any chair. Dion now picks up the object at close range.

*Transition:* (Handover) "Thanks, Zongzhe. When the robot reaches the object, it has to confirm, with the camera on its wrist, that this is the one the user looked at."

## Slide 12: CLIP finds the looked-at box across cameras, and now steers the grasp: 600 of 602

**Dion** | slot 1:35 | elapsed at end 13:50

This is the central perception problem. We have the glasses crop from slide 6, and the wrist camera sees several objects. Which one is it?

The obvious approach is keypoint matching: find distinctive points in both images and pair them. We measured that first. It ranked the box first in none of 15 pairs. The viewpoints differ too much. So we compared whole-object features, and CLIP ranked the right box first in all 25.

This week we put it where it matters, inside the grasp client. The arm now goes for the box you looked at, not the box SAM 3 is most confident about. On a scene with two cardboard boxes, the old pick took the wrong box in all 114 frames. With the glasses crop, 266 of 268 targets were the right box. With three boxes, 334 of 334. If nothing matches well enough, the arm waits.

The two misses are instructive. They came at 1.5 metres, where gaze landed on the mat. The crop was wrong before the matcher ever saw it. So the next step is to refuse weak gaze picks at the glasses.

The real limit is identical objects: two boxes of the same colour, 6 of 12. Appearance cannot separate them. That needs the gaze ray in the robot's frame, the glasses calibration from slide 8.

All of this is on replayed recordings. The real arm run comes next.

*Transition:* "Once the target mask is chosen, the arm has to pick it up."

## Slide 13: The real arm grasps on a spoken command: 5 of 6 within reach

**Dion** | slot 1:10 | elapsed at end 15:00

Grasping is a state machine. The arm only accepts a target after a grasp request, and only when idle. It then steps the wrist camera towards the target mask, two centimetres at a time, re-checking at each step, until it is 21 centimetres away. This is a simple form of visual servoing: small corrections absorb calibration and depth errors. Then it grasps, lifts, returns home, and holds the object until the user says 'release'.

Our first real grasp was on 13 October. Started from a recorded spoken command, the arm made 5 of 8 grasps. Both failures at 54.5 centimetres were out of reach, so within reach it was 5 of 6.

Safety came first. The arm's hardware stop is rejected by its controller, so we wrote a software stop. On the real arm it cancels motion within a millisecond. Every motion test still has two people and a hand on the power button.

These grasps used a simple grasping method, one blind step and close. Next we will look at the learned grasp model we used to propose more complicated grasps.

*Transition:* "The learned grasp model, AnyGrasp, is what we use for harder grasps."

## Slide 14a: AnyGrasp proposes full grasps from one point cloud, and grasped 2 of 3 at the ideal spot

**Dion** | slot 0:40 | elapsed at end 15:40

AnyGrasp is a learned grasp model. It looks at the 3D points from the depth camera and proposes hundreds of grasps: where to put the gripper, at what angle, how wide to open, and how confident it is. It was never trained on our box.

This is it running on the robot. The arm stops 21 centimetres from the box, the camera takes one view, and the grippers you see are AnyGrasp's proposals.

Its output does not drop straight into our arm. We found and fixed four mismatches before any motion: the gripper axis, the fingertip offset, a 180 degree wrist spin, and how RViz drew the grasps. With those fixed, it grasped 2 of 3 at the ideal spot. And it does propose the grasp we want, straight down across the top, in most frames.

*Transition:* "Two of three is at one spot. Moving the box is where the challenges start."

## Slide 14b: Off the ideal spot, the challenge is the close-up view: the camera sees one face

**Dion** | slot 0:45 | elapsed at end 16:25

When we moved the box, the grasps stopped working. We traced it to the view, not the model.

Here is what the camera sees at 21 centimetres. As the cloud turns, you can see it is mostly one face of the box. From that, AnyGrasp's most confident grasps go across the 75 millimetre face, and our gripper opens to 71. Our fit check should catch that, but it measures width from the visible points, so an edge looks narrow enough. On replay all 369 grasps passed it. The grasp we want, from the top, is there in most frames but scores just under our floor.

So the challenge is where we ask AnyGrasp, not AnyGrasp itself. The cheapest fix is to ask once from 40 to 50 centimetres, with the whole box in view. The second is to fuse several views, which is built and needs a retest. This decides when M1 closes.

*Transition:* (Handover) "Sherman will now step back from the parts and show what is connected today."

## Slide 15: Where each part sits in the full flow, and the links still to join

**Sherman** | slot 1:05 | elapsed at end 17:10

Here is the full flow from slide 4 again, with each part we have just shown placed where it sits.

Built and connected today: a recorded voice command starts a real grasp on the real arm, and since this week the glasses crop also chooses which object the arm goes for, on replayed recordings. My map feeds the navigation frame tree, and the memory graph is built from my recorded drive.

Two links are still to join. The robot has to explore with a live memory graph, match what it sees against the gaze target, and turn a match into a navigation goal. Nav2 has to drive the base, which I start right after this presentation.

So there is no end-to-end run yet. That matches the plan: the first closed-loop run is milestone M4, in January. Here is how we stand against that schedule.

*Transition:* Straight into slide 16, same presenter.

## Slide 16: Ahead on memory and gaze, behind on calibration and driving, final dates unchanged

**Sherman** | slot 1:10 | elapsed at end 18:20

This chart shows every milestone by week. Each one has a written test. For example, M2 is done when, with two boxes on the table, the arm picks the one you looked at three times out of four. Solid bars are work done so far, light bars are our forecast, and the grey bands are recess, exams and the winter break, when we are not working.

Our September plan expected, at this point, only the build milestone finished and the arm and base under way. We have that. The build milestone closed in week two. The arm picks up a box on the simple path. My map and localisation are done.

Three milestones started well ahead of their windows: voice and gaze to the arm, the memory graph, and the gaze-instance work. The memory graph should finish a week early.

Two things are behind, and both are mine: calibrating the base camera, because the rig is not built yet, and the test drives, because bring-up has taken twice my estimates. They slip one to two weeks into January. M8 and the final dates do not move.

The weeks after the break carry most of the integration: closed loop in January, the robot exploring in February, and the end-to-end trials in March.

*Transition:* (Handover) "Zongzhe will cover what the plan costs and what could go wrong."

## Slide 17: Budget: SGD 1,500 for compute, approved. Risks are mostly schedule and shared hardware

**Zongzhe** | slot 0:45 | elapsed at end 19:10

Our budget is small and approved: a thousand Singapore dollars for a GPU and five hundred for API credits for AI services, both for compute. The reason is concrete. Everything runs on one 16 gigabyte GPU in the lab, shared by the three of us and by the CI runner. Segmentation, grasping, CLIP, speech and two language models all need it, and the memory graph's segmentation alone peaks at over 10 gigabytes. We have never run them all at once.

The main risks are about schedule and shared hardware. If time runs short, we have a cut list fixed in advance, and the paper's smarter exploration order goes first. The grasp model's licence is tied to a machine ID, and a new one is requested. The lab machine is shared and has hung twice. And neither the arm nor the base has a working hardware stop, so every motion test has two people and a hand on the power button.

*Transition:* "To close, what happens next and what we want you to remember."

## Slide 18: Next: close the grasp, drive the base, query the graph. Then explore with gaze

**Zongzhe** | slot 0:50 | elapsed at end 20:00

In the next two weeks, before exams, we close four specific gaps. The glasses learn to refuse a weak gaze pick, and the gaze-matched grasp runs on the real arm. The new AnyGrasp version and the fused views are tested, then a twelve-trial validation closes the grasp milestone. Sherman starts driving the base with Nav2. And I run the full memory graph query on the recorded drive, checked against the answer key.

After the break, the pieces join: the two-box gaze test on the real arm, the camera calibrations, the first closed-loop run in January, and the robot exploring on its own in February, with a gaze match telling it when to stop. In March we run the end-to-end trials.

Three things to take away. The hard part of this problem is keeping the object's identity across very different viewpoints. Every subsystem now has measured results on real hardware or real data. And the remaining links are scheduled, with a cut list fixed in advance. Thank you. We are happy to take questions.

*Transition:* Into questions.

