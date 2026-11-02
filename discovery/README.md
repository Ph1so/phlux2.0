# Discovered companies

Robotics and robotics-adjacent companies that phlux does not track yet, and the job board each
one uses. Written by `python -m phlux.discovery` (weekly, `.github/workflows/discovery.yml`);
the full data is in [`candidates.json`](candidates.json).

**Last run 2026-11-01:** 382 candidates from yc, seeds · 4 already in `companies.csv` (skipped) · 74 with a job board phlux can read · 30 with internships open now · 4 boards matched by name only · 300 unresolved.

**new** marks companies first seen in this run (378).

## Adding a company

1. Paste its row into `companies.csv`.
2. Add its name to the active list, `lists/robotics.json`. The bot only scrapes companies in that list,
   so a row in `companies.csv` alone is never read.
3. Check `seed_new_companies` in `storage.json`: while it is false, the first scrape treats every
   current posting as new (only internships are emailed).

To check a company by hand: `python -m phlux.discovery detect <careers-or-company-url>`.
To have one checked every run, add a `Name,website` line to [`seeds.txt`](seeds.txt).
Boards with more than 50 postings get `->FILTER:intern` so storage keeps only internships.

## With internships open (30)

| | Company | What they do | Focus | Board | Postings | Internships | Examples |
|---|---|---|---|---|---|---|---|
| **new** | [Astranis](http://www.astranis.com) | Advanced satellites for high orbits. | adjacent | [greenhouse](https://job-boards.greenhouse.io/astranis) | 185 | 92 | Antenna Associate (Summer 2027); Antenna Associate (Winter 2027); Antenna Intern (Summer 2027) |
| **new** | [HyLight](https://www.hylight.aero/) | Unmanned airships for inspecting our critical assets | adjacent | [dover](https://app.dover.com/HyLight/careers/07e7aff2-18e8-4518-8d08-b6a6b165ea97) | 23 | 8 | Airworthiness engineer - Internship; Business Development Internship; Chief of Staff Associate Intern |
| **new** | [Inversion Space](https://www.inversionspace.com/) | Turning space into a transportation layer for Earth | adjacent | [greenhouse](https://job-boards.greenhouse.io/inversionspace) | 90 | 7 | AI & Internal Tools Software Engineer - Summer Internship 2027; Avionics Embedded Software Engineer - Summer Internship 2027; Avionics Mech… |
| **new** | [Spaceium Inc](https://spaceium.com) | In-Space Refueling | robotics | [greenhouse](https://job-boards.greenhouse.io/spaceium) | 12 | 5 | Electrical Intern (Fall 26); Electrical Intern (Summer 27); Electrical Intern (Winter 27) |
| **new** | [AstroForge](https://www.astroforge.io/) | We Mine Asteroids | robotics | [gem](https://jobs.gem.com/astroforge-io) | 15 | 4 | Asteroid Mining Intern; Guidance, Navigation, and Controls Intern; Integration & Test Engineering Intern |
| **new** | [Relling](https://relling.co) | deploying the first billion robots for manufacturing | robotics | [ashby](https://jobs.ashbyhq.com/Relling) | 12 | 4 | Business Operations Intern; Controls Engineering Intern; Robotics Software Engineering Intern |
| **new** | [Helion Energy](http://helionenergy.com) | Building the world's first fusion power plant | adjacent | [ashby](https://jobs.ashbyhq.com/helion) | 63 | 4 | Electrical Engineering Summer 2027 Intern; Materials Engineering Summer 2027 Intern; Plasma Diagnostics Summer 2027 Intern |
| **new** | [Multiply Labs](http://multiplylabs.com/) | Robotic production capacity for the pharma manufacturing industry | robotics | [lever](https://jobs.lever.co/multiplylabs) | 11 | 3 | Mechanical Engineering Co-op/Intern (Spring 2027); Robotics Software Intern; Software Intern |
| **new** | [Odys Aviation](https://www.odysaviation.com/) | Vertical takeoff and landing aircraft for major airlines | adjacent | [ashby](https://jobs.ashbyhq.com/odys-aviation) | 14 | 3 | Robotics & Embedded Systems Intern; Systems Engineering and Integration Intern; Mechanical Engineering Intern/Co-Op [Propulsion] |
| **new** | [Nox Metals](https://noxmetals.co/) | Supplying America's Industrial Base | robotics | [ashby](https://jobs.ashbyhq.com/nox-metals) | 37 | 2 | Marketing Intern; Factory Deployed Intern |
| **new** | [Revise Robotics](https://www.reviserobotics.com/) | Automating refurbishment of $1T in consumer electronics | robotics | [ashby](https://jobs.ashbyhq.com/reviserobotics) | 2 | 2 | Business Development Intern – Summer/Fall 2026; Engineering Intern — Summer/Fall 2026 |
| **new** | [Beyond Reach Labs](https://www.beyondreachlabs.com) | Space solar arrays that grow to the size of a football field in orbit | adjacent | [ashby](https://jobs.ashbyhq.com/beyondreachlabs) | 7 | 2 | Mechanical Engineer Intern (Spring 2027); Mechanical Engineer Intern (Summer 2027) |
| **new** | [General Astronautics](https://generalastro.com/) | Superintelligent space Robots | adjacent | [ashby](https://jobs.ashbyhq.com/generalastronautics) | 5 | 2 | Mechanical Engineering Internship/Co-op (Spring 2027); Mechanical Engineering Internship/Co-op (Summer 2027) |
| **new** | [H3X Technologies](http://h3x.tech/) | The lightest electric aircraft motors in the world. | adjacent | [ashby](https://jobs.ashbyhq.com/h3x-technologies) | 4 | 2 | Electromagnetics Engineering Intern (Spring); Test Engineering Intern (Spring) |
| **new** | [Pyka](https://flypyka.com) | Autonomous electric airplanes | adjacent | [lever](https://jobs.lever.co/pyka) | 15 | 2 | Electrical Engineering Internship - Winter/Spring 2027 (Early Interest); Mechanical Engineering Internship - Winter/Spring 2027 |
| **new** | [Wardstone](https://www.wardstone.us) | The Modular Interceptor Platform | adjacent | [gem](https://jobs.gem.com/wardstone-space) | 19 | 2 | Engineering Intern; MBA Intern |
| **new** | [Brumby](https://brumby.com) | Robot Cowboys that Herd Cattle with AI Drones | robotics | [ashby](https://jobs.ashbyhq.com/brumby) | 4 | 1 | Hardware Intern |
| **new** | [Fleetzero](https://www.fleetzero.com) | Making all ships robots. | robotics | [lever](https://jobs.lever.co/fleetzero) | 2 | 1 | Marketing Intern |
| **new** | [Human Archive](https://www.humanarchive.ai/) | Physical AI data lab | robotics | [ashby](https://jobs.ashbyhq.com/humanarchive) | 21 | 1 | Founder's Office Intern - Partnerships |
| **new** | [Innate](https://innate.bot) | Personal AI Robots | robotics | [ashby](https://jobs.ashbyhq.com/innate) | 3 | 1 | Content & Marketing Intern |
| **new** | [One Robot](https://www.onerobot.io/) | World models for robot evals and training. | robotics | [ashby](https://jobs.ashbyhq.com/onerobot) | 3 | 1 | Machine Learning Intern |
| **new** | [Overview](https://overview.ai) | Reshaping industrial quality with AI, hardware, and software | robotics | [ashby](https://jobs.ashbyhq.com/overview) | 62 | 1 | Engineering Intern |
| **new** | [Pivot Robotics](https://pivotrobotics.com) | AI for Robot Arms in Factories | robotics | [ashby](https://jobs.ashbyhq.com/pivotrobotics) | 5 | 1 | Robot Operator Internship (Part-Time) |
| **new** | [Shinkei Systems](http://www.shinkei.systems) | Robots for longer-lasting, better-tasting fish at scale. | robotics | [kula](https://careers.kula.ai/shinkei) | 16 | 1 | Mechanical Engineering Intern/Associate Engineer |
| **new** | [Sorting Robotics](https://www.sortingrobotics.com/) | We create automation technology for the cannabis industry. | robotics | [workable](https://apply.workable.com/sorting-robotics/) | 8 | 1 | Robotics Engineering Co-Op Internship |
| **new** | [Verne Robotics](https://vernerobotics.com/) | AI models that teach robots new skills in hours | robotics | [ashby](https://jobs.ashbyhq.com/Verne%20Robotics) | 6 | 1 | Engineering Intern |
| **new** | [Apolink](https://apolink.space) | 24/7 satellite connectivity in low Earth orbit | adjacent | [ashby](https://jobs.ashbyhq.com/apolink) | 2 | 1 | Internship General App |
| **new** | [Boom](https://boomsupersonic.com/) | Economically and environmentally sustainable supersonic travel | adjacent | [rippling](https://ats.rippling.com/boom-supersonic/jobs) | 29 | 1 | Summer 2027 Engineering and Tech Internship |
| **new** | [Orbital Operations](https://www.orbitalops.tech/) | High Thrust Space Vehicles for Satellite Defense | adjacent | [greenhouse](https://job-boards.greenhouse.io/orbitaloperations) | 5 | 1 | Summer 2027 Internship - Engineering |
| **new** | [Singularity](https://www.singularityus.com/) | Building and Protecting an Exciting Future | adjacent | [rippling](https://ats.rippling.com/singularity-defense/jobs) | 28 | 1 | Mechanical Engineer - Co-op |

```csv
Astranis,https://job-boards.greenhouse.io/astranis,@greenhouse->FILTER:intern
HyLight,https://app.dover.com/HyLight/careers/07e7aff2-18e8-4518-8d08-b6a6b165ea97,@dover
Inversion Space,https://job-boards.greenhouse.io/inversionspace,@greenhouse->FILTER:intern
Spaceium,https://job-boards.greenhouse.io/spaceium,@greenhouse
AstroForge,https://jobs.gem.com/astroforge-io,@gem
Relling,https://jobs.ashbyhq.com/Relling,@ashby
Helion Energy,https://jobs.ashbyhq.com/helion,@ashby->FILTER:intern
Multiply Labs,https://jobs.lever.co/multiplylabs,@lever
Odys Aviation,https://jobs.ashbyhq.com/odys-aviation,@ashby
Nox Metals,https://jobs.ashbyhq.com/nox-metals,@ashby
Revise Robotics,https://jobs.ashbyhq.com/reviserobotics,@ashby
Beyond Reach Labs,https://jobs.ashbyhq.com/beyondreachlabs,@ashby
General Astronautics,https://jobs.ashbyhq.com/generalastronautics,@ashby
H3X Technologies,https://jobs.ashbyhq.com/h3x-technologies,@ashby
Pyka,https://jobs.lever.co/pyka,@lever
Wardstone,https://jobs.gem.com/wardstone-space,@gem
Brumby,https://jobs.ashbyhq.com/brumby,@ashby
Fleetzero,https://jobs.lever.co/fleetzero,@lever
Human Archive,https://jobs.ashbyhq.com/humanarchive,@ashby
Innate,https://jobs.ashbyhq.com/innate,@ashby
One Robot,https://jobs.ashbyhq.com/onerobot,@ashby
Overview,https://jobs.ashbyhq.com/overview,@ashby->FILTER:intern
Pivot Robotics,https://jobs.ashbyhq.com/pivotrobotics,@ashby
Shinkei Systems,https://careers.kula.ai/shinkei,@kula
Sorting Robotics,https://apply.workable.com/sorting-robotics/,@workable
Verne Robotics,https://jobs.ashbyhq.com/Verne%20Robotics,@ashby
Apolink,https://jobs.ashbyhq.com/apolink,@ashby
Boom,https://ats.rippling.com/boom-supersonic/jobs,@rippling
Orbital Operations,https://job-boards.greenhouse.io/orbitaloperations,@greenhouse
Singularity,https://ats.rippling.com/singularity-defense/jobs,@rippling
```

## With a job board, no internships right now (44)

| | Company | What they do | Focus | Board | Postings |
|---|---|---|---|---|---|
| **new** | [Encord](https://encord.com) | The data layer for physical AI | robotics | [ashby](https://jobs.ashbyhq.com/encord) | 35 |
| **new** | [Aerones](http://www.aerones.com) | Robotics for wind turbine maintenance. | robotics | [workable](https://apply.workable.com/aerones/) | 22 |
| **new** | [Skyways](http://skyways.com) | Creating a new form of air transportation to advance our civilization | robotics | [lever](https://jobs.lever.co/skyways) | 20 |
| **new** | [Ultra](https://ultra.tech) | Practical, general-purpose robots for repetitive industrial tasks | robotics | [gem](https://jobs.gem.com/ultra) | 18 |
| **new** | [Charge Robotics](https://chargerobotics.com/) | Robots that build solar farms | robotics | [ashby](https://jobs.ashbyhq.com/charge-robotics) | 13 |
| **new** | [CircuitHub](https://circuithub.com) | On-Demand Electronics Manufacturing | robotics | [ashby](https://jobs.ashbyhq.com/circuithub) | 10 |
| **new** | [Neuron Industries](https://neuronindustries.com) | Industrial Controllers built for AI | robotics | [gem](https://jobs.gem.com/neuron) | 9 |
| **new** | [Corvus Robotics](https://www.corvus-robotics.com) | Autonomous drones to help warehouses scan inventory. | robotics | [ashby](https://jobs.ashbyhq.com/corvus-robotics) | 8 |
| **new** | [Loombotic](https://www.loombotic.com) | Wire Harnesses in as little as 7 days | robotics | [dover](https://app.dover.com/jobs/loombotic) | 8 |
| **new** | [Cosmic Robotics](https://www.cosmicrobotics.com/) | Autonomous construction on Earth and beyond | robotics | [ashby](https://jobs.ashbyhq.com/cosmic-robotics) | 5 |
| **new** | [Andromeda Surgical](http://www.andromedasurgical.com) | Autonomous surgical robots | robotics | [ashby](https://jobs.ashbyhq.com/andromedasurgical) | 3 |
| **new** | [Atum Works](https://atum.works/) | Gigascale Nanomanufacturing | robotics | [ashby](https://jobs.ashbyhq.com/atumworks) | 3 |
| **new** | [Volta Labs, Inc.](http://voltalabs.com) | Unlocking the utility of genomics for the world. | robotics | [lever](https://jobs.lever.co/voltalabs) | 3 |
| **new** | [AON3D](https://www.aon3d.com) | Additive Manufacturing with advanced materials | robotics | [greenhouse](https://job-boards.greenhouse.io/aon3d-fr) | 2 |
| **new** | [Boost Robotics](https://www.boostrobotics.ai) | Robots for the inspection and maintenance of data centers | robotics | [gem](https://jobs.gem.com/boost-robotics) | 2 |
| **new** | [JITX](http://www.jitx.com) | Automatic circuit board design. | robotics | [lever](https://jobs.lever.co/jitxinc) | 2 |
| **new** | [Tekton Dynamics](https://www.tekton-dynamics.com) | AI control layer for welding robots | robotics | [ashby](https://jobs.ashbyhq.com/tekton-dynamics) | 2 |
| **new** | [Azalea Robotics Corporation](https://azalearobotics.com/) | Automating airport baggage handling with robots. | robotics | [dover](https://app.dover.com/jobs/azalearobotics) | 1 |
| **new** | [Duranium](https://www.duranium.co/) | Reshoring critical metal production | robotics | [dover](https://app.dover.com/jobs/duranium) | 1 |
| **new** | [Lucid Bots](https://lucidbots.com/) | We build robots for dull, dirty, and dangerous jobs. | robotics | [ashby](https://jobs.ashbyhq.com/lucidbots) | 1 |
| **new** | [Paladin](http://paladindrones.io) | We deploy autonomous drones to 911 calls. Our software gives first… | robotics | [jazzhr](https://paladindrones.applytojob.com/apply) | 1 |
| **new** | [Tuesday Labs](https://www.tuesdaylabs.com) | Delightful robots | robotics | [ashby](https://jobs.ashbyhq.com/tuesday-labs) | 1 |
| **new** | [Vorticity](http://vorticity.xyz/) | The Fastest Scientific Computing Platform on the Planet | robotics | [ashby](https://jobs.ashbyhq.com/vorticity) | 1 |
| **new** | [Atomic Industries](http://atomic.industries) | Software orchestrated mass production of plastics | robotics | [ashby](https://jobs.ashbyhq.com/atomicindustries) | 0 |
| **new** | [Efference](https://efference.ai) |  | robotics | [ashby](https://jobs.ashbyhq.com/efference) | 0 |
| **new** | [Pave Robotics](https://pave-robotics.com) | Robots that repair roads | robotics | [ashby](https://jobs.ashbyhq.com/pave-robotics) | 0 |
| **new** | [Astro Mechanica](https://astromecha.co/) | Supersonics for the new Jet Age | adjacent | [ashby](https://jobs.ashbyhq.com/Astro-Mechanica) | 40 |
| **new** | [REGENT](http://regentcraft.com) | All-electric seagliders for fast, affordable regional transportation | adjacent | [ashby](https://jobs.ashbyhq.com/regent) | 34 |
| **new** | [Curri](http://www.curri.com) | Construction & industrial logistics platform. | adjacent | [ashby](https://jobs.ashbyhq.com/curri) | 24 |
| **new** | [Icarus](https://www.icarus.one/) | Stratospheric birds for defense | adjacent | [greenhouse](https://job-boards.greenhouse.io/icarus) | 22 |
| **new** | [Quindar](https://www.quindar.space) | Datadog for Space | adjacent | [ashby](https://jobs.ashbyhq.com/quindar) | 19 |
| **new** | [Hubble Network](https://hubble.com) | Bluetooth to Space | adjacent | [greenhouse](https://job-boards.greenhouse.io/hubblenetwork) | 17 |
| **new** | [Turion Space](https://turionspace.com/) | Moving Things Around in Space, Imaging Space Objects When We're Not | adjacent | [ashby](https://jobs.ashbyhq.com/turion-space) | 15 |
| **new** | [Luminate](http://www.luminatemed.com) | We make cancer care at home possible. | adjacent | [bamboohr](https://luminatemedical.bamboohr.com/careers) | 7 |
| **new** | [Inflection Space Systems](https://inflection-space.com/) | Hyperscaling space manufacturing | adjacent | [rippling](https://ats.rippling.com/inflection-space/jobs) | 6 |
| **new** | [Meticulous](https://www.meticulous.ai) | Automated e2e screenshot testing without writing or maintaining tests | adjacent | [ashby](https://jobs.ashbyhq.com/meticulous) | 6 |
| **new** | [Albedo](https://albedo.com) | Full-stack VLEO satellite missions | adjacent | [greenhouse](https://job-boards.greenhouse.io/albedo) | 5 |
| **new** | [Epsilon3](https://www.epsilon3.io/) | AI-Powered ERP, MES, and Test Software for Complex Operations | adjacent | [lever](https://jobs.lever.co/epsilon3) | 4 |
| **new** | [Heart Aerospace](http://www.heartaerospace.com) | Heart makes electric airplanes with an all-electric range of 250 miles | adjacent | [greenhouse](https://job-boards.greenhouse.io/heartaerospace) | 4 |
| **new** | [Maritime Fusion](https://maritimefusion.com) | Fusion reactors for ships | adjacent | [gusto](https://jobs.gusto.com/boards/maritime-fusion-34d86452-e58d-44d8-86b9-39b654807910) | 4 |
| **new** | [Farcast](https://www.farcast.com/) | We build advanced satcom user terminals | adjacent | [lever](https://jobs.lever.co/Farcast) | 3 |
| **new** | [Mindstate Design Labs](http://mindstate.design) | Programmable biology company for psychoactive effect design | adjacent | [rippling](https://ats.rippling.com/mindstate-design-labs/jobs) | 1 |
| **new** | [Seabound](http://seabound.co) | Carbon capture equipment for ships | adjacent | [dover](https://app.dover.com/jobs/seabound) | 0 |
| **new** | [Sorcerer](https://sorcerer.earth) | Building a nervous system for the atmosphere | adjacent | [ashby](https://jobs.ashbyhq.com/sorcerer) | 0 |

```csv
Encord,https://jobs.ashbyhq.com/encord,@ashby
Aerones,https://apply.workable.com/aerones/,@workable
Skyways,https://jobs.lever.co/skyways,@lever
Ultra,https://jobs.gem.com/ultra,@gem
Charge Robotics,https://jobs.ashbyhq.com/charge-robotics,@ashby
CircuitHub,https://jobs.ashbyhq.com/circuithub,@ashby
Neuron Industries,https://jobs.gem.com/neuron,@gem
Corvus Robotics,https://jobs.ashbyhq.com/corvus-robotics,@ashby
Loombotic,https://app.dover.com/jobs/loombotic,@dover
Cosmic Robotics,https://jobs.ashbyhq.com/cosmic-robotics,@ashby
Andromeda Surgical,https://jobs.ashbyhq.com/andromedasurgical,@ashby
Atum Works,https://jobs.ashbyhq.com/atumworks,@ashby
Volta Labs,https://jobs.lever.co/voltalabs,@lever
AON3D,https://job-boards.greenhouse.io/aon3d-fr,@greenhouse
Boost Robotics,https://jobs.gem.com/boost-robotics,@gem
JITX,https://jobs.lever.co/jitxinc,@lever
Tekton Dynamics,https://jobs.ashbyhq.com/tekton-dynamics,@ashby
Azalea Robotics Corporation,https://app.dover.com/jobs/azalearobotics,@dover
Duranium,https://app.dover.com/jobs/duranium,@dover
Lucid Bots,https://jobs.ashbyhq.com/lucidbots,@ashby
Paladin,https://paladindrones.applytojob.com/apply,@jazzhr
Tuesday Labs,https://jobs.ashbyhq.com/tuesday-labs,@ashby
Vorticity,https://jobs.ashbyhq.com/vorticity,@ashby
Atomic Industries,https://jobs.ashbyhq.com/atomicindustries,@ashby
Efference,https://jobs.ashbyhq.com/efference,@ashby
Pave Robotics,https://jobs.ashbyhq.com/pave-robotics,@ashby
Astro Mechanica,https://jobs.ashbyhq.com/Astro-Mechanica,@ashby
REGENT,https://jobs.ashbyhq.com/regent,@ashby
Curri,https://jobs.ashbyhq.com/curri,@ashby
Icarus,https://job-boards.greenhouse.io/icarus,@greenhouse
Quindar,https://jobs.ashbyhq.com/quindar,@ashby
Hubble Network,https://job-boards.greenhouse.io/hubblenetwork,@greenhouse
Turion Space,https://jobs.ashbyhq.com/turion-space,@ashby
Luminate,https://luminatemedical.bamboohr.com/careers,@bamboohr
Inflection Space Systems,https://ats.rippling.com/inflection-space/jobs,@rippling
Meticulous,https://jobs.ashbyhq.com/meticulous,@ashby
Albedo,https://job-boards.greenhouse.io/albedo,@greenhouse
Epsilon3,https://jobs.lever.co/epsilon3,@lever
Heart Aerospace,https://job-boards.greenhouse.io/heartaerospace,@greenhouse
Maritime Fusion,https://jobs.gusto.com/boards/maritime-fusion-34d86452-e58d-44d8-86b9-39b654807910,@gusto
Farcast,https://jobs.lever.co/Farcast,@lever
Mindstate Design Labs,https://ats.rippling.com/mindstate-design-labs/jobs,@rippling
Seabound,https://app.dover.com/jobs/seabound,@dover
Sorcerer,https://jobs.ashbyhq.com/sorcerer,@ashby
```

## Matched by name only — check before adding (4)

A board under the company's name exists, but nothing on it names the company's site,
so it may belong to a same-name company. Open the board before pasting its row.

| | Company | What they do | Focus | Board | Postings | Internships | Examples |
|---|---|---|---|---|---|---|---|
| **new** | [Preload](https://preload.ai) | Sensorimotor context for physical AI | robotics | [greenhouse](https://job-boards.greenhouse.io/preload) | 9 | 0 |  |
| **new** | [Shepherd Robotics](https://shepherdrobotics.ai/) | Robots for high skilled labor powering AI infrastructure | robotics | [greenhouse](https://job-boards.greenhouse.io/shepherd) | 0 | 0 |  |
| **new** | [Weave Robotics](https://www.weaverobotics.com) | Practical and delightful home robots | robotics | [greenhouse](https://job-boards.greenhouse.io/weave) | 3 | 0 |  |
| **new** | [Remora](https://www.remoracarbon.com) | Modular carbon capture | adjacent | [greenhouse](https://job-boards.greenhouse.io/remoracarbon) | 9 | 0 |  |

```csv
Preload,https://job-boards.greenhouse.io/preload,@greenhouse
Shepherd Robotics,https://job-boards.greenhouse.io/shepherd,@greenhouse
Weave Robotics,https://job-boards.greenhouse.io/weave,@greenhouse
Remora,https://job-boards.greenhouse.io/remoracarbon,@greenhouse
```

## Unresolved (300)

No board phlux can read was found. Some have none (small teams hiring by email);
others use a job system phlux has no reader for, or block scripted visits.
84 say on YC that they are hiring; their YC jobs pages are linked.

| | Company | What they do | Focus | Why |
|---|---|---|---|---|
| **new** | [6thSense](https://6thsense.dev) | Nervous System for Physical AI | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Advanced Metal Research](https://advancedmetalresearch.com/) | Machine intelligence for American Welding | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Agency Tool Company](https://agencytool.com) | Reliable infrastructure to build, deploy and manage real-world robots. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Aktoria Robotics](https://aktoria.com/) | Human as API for robots | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/aktoria-robotics/jobs) |
| **new** | [Albacore Inc.](https://www.albacore.inc) | Drone submarines | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Alchemy](http://www.alchemynano.com) | Nanotechnology-enabled coatings for automotive and defence sectors | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [AlgoSurg Inc](http://www.algosurg.ai) | Surgical AI for medical device companies: Patient scan to robot-ready… | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Allus AI](https://allus.ai) | Transforming manufacturing with our next-gen Vision Foundation Model | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/allus-ai/jobs) |
| **new** | [Almond](https://almond.bot/) | America's robot factory | robotics | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/almond-2/jobs) |
| **new** | [Antropi Robotics](https://www.antropi.world/) | Autonomous CNC factories for faster hardware | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Applied Kinetics](https://appliedkinetics.ai) | AI-native manufacturing for data center and energy projects | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [ArchForm](http://archform.com) | Replacing orthodontic braces with our clear aligner and software | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/archform/jobs) |
| **new** | [Archgen Labs](https://www.archgen.tech/) | AI-powered EDA tools for faster, cooler 3D chips | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Aseon Labs](https://www.aseonlabs.com/) | Robotic pitstops for self-driving cars | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/aseon-labs/jobs) |
| **new** | [Asim](https://www.asim-group.com) | Enable robots to operate safely in the real world. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Asimov](https://tryasimov.ai/) | Real-world human movement data for humanoid robots | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/asimov/jobs) |
| **new** | [autarc](https://www.autarc.energy/global) | autarc is the agentic OS for energy installers. | robotics | uses Personio, which phlux has no reader for |
| **new** | [AutoPallet Robotics](https://autopallet.bot) | We make robots that move boxes in warehouses | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Autumn Labs](https://www.autumnlabs.io/) | Datadog for industrial robots | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Aviern](https://aviern.com/) | Unmanned cargo airplanes | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Avion](http://www.avion.health) | Avion builds and operates autonomous eVTOL drones that deliver vital… | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Axal](https://www.axal.ai/) | We assemble PCBs in under 48 hours for quantities under 10 | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Axial](https://axialcompute.com) | Accelerated Physics Kernels for Computational Engineering | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Axonnic](https://www.axonnic.com) | Bringing human dexterity to every robot | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [b12 Labs](https://b12-labs.com/) | Making hard molecules for Pharma and Biotech | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/b12-labs/jobs) |
| **new** | [Beanstalk](http://beanstalk.farm) | Great tasting produce, farmed around the corner | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Bite Ninja](http://www.biteninja.com) | Remote labor for restaurants | robotics | uses YC Work at a Startup, which phlux has no reader for |
| **new** | [BotBuilt](https://www.botbuilt.com) | We use robots to build houses. | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/botbuilt/jobs) |
| **new** | [Bramante](https://www.bramantebio.com) | Life sciences reagents and software | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Bucket Robotics](https://bucket.bot) | Defect detection for manufacturing built from CAD and synthetic data. | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/bucket-robotics/jobs) |
| **new** | [Buoyant Aero](https://www.buoyant.aero) | Bringing back blimps | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/buoyant-aero/jobs) |
| **new** | [ChemPilot.ai](https://chempilot.ai/) | Discover novel defense related materials/molecules. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [chrt](https://chrt.com) | chrt is a logistics platform for time-critical shipping | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Colony](https://colony.tech) | Long-range drone network for world data collection | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Cortex AI](https://cortexrobot.ai/) | Large-scale real-world robot & human data for embodied AI | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Daedalus](https://daedalus.de) | AWS for precision manufacturing | robotics | site unreachable: https://daedalus.de/ unreachable (SSLError) |
| **new** | [Dartboard](https://dartboard.ai) | AI-native remote operations center for hardware fleets | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Darwin](https://darwinrobotics.ai) | Robot technicians for AI infrastructure | robotics | no board linked from its site (8 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/darwin/jobs) |
| **new** | [Datoric](https://www.datoric.com) | The training data R&D engine for physical AI | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Dawn Industries](https://www.dawnxr.com) | Automatic Diagnosis & Fix for Industrial Automation Cells | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [DeepAware AI (Robotics Center of Silicon Valley)](https://roboticscenter.ai/) | Robots, parts & RL envs & evals - delivered in 48 hrs / pickup in SF. | robotics | no board linked from its site (8 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/deepaware-ai-robotics-center-of-silicon-valley/jobs) |
| **new** | [DeepReach Inc.](http://www.deepreach.ai) | Network for Physical AI Data Business | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/deepreach-inc/jobs) |
| **new** | [Degla Inc](https://degla.ai) | The fully autonomous intelligence layer in the sky. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Deploy](https://deployrobotics.co/) | The generalist robot deployment company. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Double Robotics](https://doublerobotics.com) | Telepresence robots | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Dreamscale Labs](https://dreamscalelabs.com) | Real-time cloud inference for robotics. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Earendil Robotics](https://earendil.io) | Drone swarm defence at a small-unit level | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Eden Robotics](https://www.edenrobotics.ai) | Autonomous services for humanity. | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/eden-robotics/jobs) |
| **new** | [Edgerun](https://edgerun.com) | Military exoskeletons | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/edgerun/jobs) |
| **new** | [Elodin](https://elodin.systems/) | Unified flight software and hardware for the mission of tomorrow | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Ember Robotics](https://www.emberrobotics.com) | Datadog for robots | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Enact](https://enact.company) | Real-world RL environments for robotics models | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Evident Machines](https://evidentmachines.com/) | Real-world benchmarks for electrical engineering | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Fern](https://fern.bot) | RL environments for robotics companies | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | Flirtey (SkyDrop) | Flirtey is the world’s first commercial drone delivery service and… | robotics | no website, and no board found under its name |
| **new** | [Flux Auto](https://fluxauto.ai) | Physical AI for Warehouses and Factories | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Flywheel AI](https://useflywheel.ai/) | Waymo for excavators | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Forerunner](https://tryforerunner.com) | Quick-turn bent tube shop for aerospace, energy, industrials | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Forge Automation](https://www.forgeautomation.ca) | Software Enabled CNC Parts Supplier | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/forge-automation/jobs) |
| **new** | [Forge Robotics](https://forge-robotics.com) | A robotics intelligence system for metal fabrication | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Four Growers](https://fourgrowers.com/) | Robots that feed the world - robotic harvesting and analytics | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Genecis Bio](https://www.genecis.co/) | Makes guilt-free plastics from food waste | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [General Aviation Company](https://generalaviation.com) (tracked *General Motors* is a similar name) | Fixing air traffic control with remote towers | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [General Instinct](https://general-instinct.com/) | Deployment infrastructure for Physical AI | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [General Trajectory](https://www.generaltrajectory.com/) | AI for the physical world | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [GreaseBoss](https://www.greaseboss.com.au) | GreaseBoss verifes industrial machinery is greased correctly | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Greypoint Industries](https://greypointindustries.com/) | Building drone swarms that hunt hidden enemies. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Grip](https://www.griprobotics.ai) | Robots for waste manipulation | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Guardian RF](https://guardianrf.com/) | Drone detection for US defense and national security | robotics | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/guardian-rf/jobs) |
| **new** | [HABIT](https://habit.inc) | Accelerating world models. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Hebbian Robotics](https://hebbianrobotics.com/) | Foundational infrastructure for Physical AI | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Hedgehog](http://hedgehogfoods.com) | Building robotic mushroom farms | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Hemlock](https://hemlock.inc) | Force + contact dynamics collected at scale for training physical AI. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Hermes Robotics](http://hermes-robotics.com) | Autonomous street sweeping as a service by retro-fitting vehicles | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Hilstart](https://hilstart.io/) | Autonomous Hardware Testing | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [horizontal.](https://horizontal-tech.com) | AI agents that run factory operations end-to-end. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Hub](https://hub.xyz) | Real-world training data for frontier AI labs and robotics. | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/hub/jobs) |
| **new** | [Hundred](http://hundred.systems/) | 100% automated inspection for precision hardware parts | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Illuminant Surgical](https://www.illuminant.ai/) | A new way of seeing inside the human body. | robotics | uses YC Work at a Startup, which phlux has no reader for |
| **new** | [IMPACT Drones](https://www.impact-drones.com) | Air Defense as a Service for Civilian Infrastructure. | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/impact-drones/jobs) |
| **new** | [Impossible Metals](https://impossiblemetals.com) | Underwater robotic vehicles that collect battery metals responsibly | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Industrial Next](https://www.industrialnext.ai) | IndustrialNext builds the AI brain for manufacturing –… | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [InLoop Robotics](https://inloop-robotics.com/) | Robotic arms that pick and pack your orders. | robotics | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/inloop-robotics/jobs) |
| **new** | [Intelligence Factory](https://intelligence-factory.com) | Human Intelligence for Robots | robotics | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/intelligence-factory/jobs) |
| **new** | [Intelline](https://www.intelline.ca/) | Intelline makes the world's most efficient fuel agnostic engines for… | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/intelline/jobs) |
| **new** | [Inversion Semiconductor](https://www.inversionsemi.com) | Manufacturing the most powerful chips, 15x faster | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Iron Grid](https://getirongrid.com/) | AI-Native Data Center Engineering | robotics | site blocked: Cloudflare bot wall on https://www.getirongrid.com/jobs |
| **new** | [Isengard Industries Inc](http://isengardindustries.com/) | Mass-produced AI strike systems and Counter-UAS | robotics | uses YC Work at a Startup, which phlux has no reader for |
| **new** | [JetPack Aviation](http://www.jetpackaviation.com) | Flying motorcycles | robotics | site unreachable: http://www.jetpackaviation.com/ unreachable (SSLError) |
| **new** | [Kairox Systems](http://www.kairoxsys.com/) | Autonomous drones that fly and swim | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Kalam Labs](http://www.kalamlabs.in) | Autonomous Stratospheric UAVs | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/kalam-labs/jobs) |
| **new** | [Libra Robotics](https://www.librabots.com/) | The robot workforce for infrastructure of the AI era | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Lightberry](https://lightberry.com) | Robots with soul | robotics | no board linked from its site (8 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/lightberry/jobs) |
| **new** | [Linewise](https://linewise.io/) | Industrial data layer for physical RSI | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Lux Foods](https://www.luxfoods.xyz) | Crops engineered for premium fruit, grown without sunlight. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Manifold](https://www.manifoldindustries.ai/) | Drop-in robotic labor that works on Day 1 | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | Mantle | The pit crew for machines and robots. | robotics | no website, and no board found under its name |
| **new** | [Mars Auto](https://marsauto.com) | Autonomous trucks to fully automate long-haul freight shipping | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Mass Magnetics](https://massmagnetics.com/) | USA-made magnetics for robotics and defense. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Mbodi AI](https://www.mbodi.ai/) | Industrial Robots that Learn and Operate Like Humans | robotics | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/mbodi-ai/jobs) |
| **new** | [Meter Feeder](http://www.meterfeeder.com) | Helping fleets find and pay parking tickets | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Micora](https://micora.com) | Micro-grids in a box deploying industrial power autonomously in weeks | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Milliray](https://milliray.com/) | Technology to detect and track small drones | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Miru](https://www.mirurobotics.com) | Config Management for Robotics | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Mobius Materials](https://www.mobiusmaterials.com) | The spot market for semiconductors | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Morphle Labs](https://morphlelabs.com) | Robotic Automation for cancer diagnostics - Robotic Microscopes &… | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/morphle-labs/jobs) |
| **new** | [MorphoAI](https://morpho.ai/) | Software tool for designing robots and machines | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/morphoai/jobs) |
| **new** | [Most Robotic](https://mostrobotic.com/) | Research lab building the most robotic household in the world | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Moving Atoms](https://movingatoms.ai/) | Scan to 3D Model | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Nebullam (DBA Clayton Farms)](http://ClaytonFarms.com) | We put farms inside restaurants, so customers get healthier food and… | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Neuromorphic](https://www.neuromorphic.vision/) | Building robots to automate wetlabs | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/neuromorphic/jobs) |
| **new** | [Nextera Robotics \| DIDGE.ai](https://nexterarobotics.com) | AI-native Robotics | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/nextera-robotics-didgeai/jobs) |
| **new** | [Nine Fives](https://ninefives.com/) | RF test equipment for next-gen spacecraft, drones, and cellphones | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/nine-fives/jobs) |
| **new** | [Nori](http://norirobotics.com) | The most capable American-made humanoid robot for $1,688 | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/noril1/jobs) |
| **new** | [Null Labs](https://n0labs.com) | End-to-end Simulation for Defense Autonomy | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Nuum Robotics](https://nuumrobotics.com/) | Snake-like robots for maintenance inside machinery. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Observant AI](https://www.observantai.com) | iPhone-based driver monitoring for commercial fleets. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Odin Robotics](https://odin-robotics.com) | Robot arms that do repetitive manual work in existing factories. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Open Actuation](https://openactuation.com) | Quick-turn, purpose-built motors & actuators for all | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Opentrons](http://opentrons.com) | We make robots for biologists. | robotics | uses Jobvite, which phlux has no reader for |
| **new** | [OpenVector](https://openvector.com) | AI that turns any camera to an autonomous worker with real-time vision | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Orangewood Labs](http://www.orangewood.co) | Orangewood builds amazing robots that people want. | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/orangewood-labs/jobs) |
| **new** | [Ornadyne](https://ornadyne.com/) | We're building robot birds for surveillance. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [OS3](https://os3robotics.com/) | Affordable, intelligent humanoid robots built to deploy at scale | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/os3/jobs) |
| **new** | [Pacific](https://pacific.space) | Robotic factories to mass produce data centers | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Parametric](https://parametric.company/) | Physical businesses that run themselves | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/parametric/jobs) |
| **new** | [Perceptive Technologies](https://www.perceptive.io) | Automated tooth cutting for dentists using imaging, AI and robotics | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [PerfectBit, Inc.](https://perfectbit.ai) | Robotics | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/perfectbit-inc/jobs) |
| **new** | [Persist AI](http://www.persist-ai.com) | Developing long-lasting drug formulations 50% faster | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Phases](https://phases.ai) | AI for the physical world | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Philon](https://philon.ai/) | General Purpose Robots | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Physical Turing](https://physicalturing.ai/) | Next generation robot deployer | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Pide Directo](http://pidedirecto.mx) | One-stop-shop for restaurants to operate and grow their business. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Piggy Robotics](https://piggyrobotics.com) | Humanoid robots that do your chores for the price of an iPhone! | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Polymath Robotics](http://www.polymathrobotics.com) | General Autonomy for Industrial Vehicles | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/polymath-robotics/jobs) |
| **new** | [Pop Meals](https://popmeals.com) | Pop Meals is a restaurant chain without chefs. All recipes are… | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/pop-meals/jobs) |
| **new** | [Primordiant](https://primordiant.com) | Embodied Scientific Intelligence | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Proception Inc](https://proception.ai/) | Making humanoids dexterous enough to thread a needle | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/proception-inc/jobs) |
| **new** | [Proprio Robotics](https://www.propriorobotics.com/) | Robots to maintain and assemble data centers | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [ProvenMetal](https://provenmetal.com) | AI-native electronics manufacturing for the American industrial base | robotics | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/provenmetal/jobs) |
| **new** | [Radical](https://www.radicalaero.com/) | Building persistent, high-performance infrastructure in the sky | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Relari](https://www.relari.ai/) | Building dexterous robots that learn from human biomechanics | robotics | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/relari/jobs) |
| **new** | [Remy AI](https://www.tryremy.ai/) | Automating dexterous tasks in warehouses with AI-powered robots | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Reshape Biotech](http://reshapebiotech.com/) | Robots that automate the everyday tasks of microbiologists. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Revolve Surgical](https://revolvesurgical.com/) | Surgical robotics for every operating room | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Rhem Labs](https://rhem.ai) | Home care technology for aging parents and their families | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/rhem-labs/jobs) |
| **new** | [RMFG](https://www.rmfg.com) | Advanced Contract MFG for fast moving hardware companies | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Robocurve](https://robocurve.org) | Evals for robots | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [Rodeo Robotics](https://www.rodeorobotics.com/) | Robots for vehicle maintenance. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Rownd](https://rownd.ai) | Fully autonomous defense solutions for the global edge. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Runtime.si](https://runtime.si/) | Evaluation Infrastructure for Robotics (YC F26) | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/runtimesi/jobs) |
| **new** | [Salem Robotics Inc](https://salemroboticsinc.com) | Deploying robots to replace workers in hazardous spaces | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Saphira AI](https://saphira.ai) | The Enablement Layer for Physical AI | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/saphira-ai/jobs) |
| **new** | [Seaflight Technologies](https://www.seaflight.tech) | We make the world's most efficient aircraft | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Seeing Systems](https://www.seeing-systems.com) | Modular AI-Commanded Drones for Defence | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/seeing-systems/jobs) |
| **new** | [Sensei](https://senseirobotics.com) | Robotic Training Data at Scale | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Servo7](https://servo7.com) | Container unloading robots for warehouses | robotics | no board linked from its site (8 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/servo7/jobs) |
| **new** | [Shiraz AI](https://shiraz.ai) | Robots that learn on the job | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [shotwell.ai](http://shotwell.ai/) | Annotations for robotics data | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Silica](https://silicamachines.com/) | Actuators for Physical AI | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Sinovia Technologies](http://www.sinoviatech.com) | Flexible printed OLED displays. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Sinter](https://sinter.systems) | Accelerated plastics manufacturing | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Skyscrape](http://skyscrape.us) | Skyscrape makes temperature-responsive insulation | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [SOMATIC](http://getsomatic.com) | Bathroom cleaning robots for office buildings. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Splash Inc.](https://splash9.com/) | Autonomous patrol-boats for National Security | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/splash-inc/jobs) |
| **new** | [SRTX](https://www.srtxlabs.com/) | Powering a better future for textiles. | robotics | site unreachable: https://www.srtxlabs.com/ unreachable (ConnectionError) |
| **new** | [StableBrowse](https://stablebrowse.ai/) | Building the Data Infrastructure layer for Physical AI. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Streamline Systems](https://streamlinesystems.ltd/) | Precision navigation for UAVs operating without GPS. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [StrideQ](https://strideq.com) | Automated phone ordering system for restaurants | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Super Powers Mobility (SPM)](https://www.spm.us) | The highest performance modular battery packs for mobility/vehicles | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/super-powers-mobility-spm/jobs) |
| **new** | [Switchboard](https://www.onswitchboard.com) | Technology for Trucking | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Synapse Semiconductor](https://synapsesemi.org) | New semiconductors that merge compute and vision | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/synapse-semiconductor/jobs) |
| **new** | [Synphony](https://www.synphony.co/) | robots & software for farms | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Taobotics](http://www.taobotics.com) | Autonomous robots for retails. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [teaBOT](http://teaBOT.com) | A robot that makes tea! | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Tenet Industries](https://www.tenetindustries.com) | AI-automated factory for PCBAs | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Tensr](https://tensr.com/) | Robotic factories that build robots | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Terraferma](https://terraferma.ai) | The world's best protein manufacturing platform. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [The Robot Learning Company](https://www.robot-learning.co/) | Tools for the next era of physical automation. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [ThereCraft](https://therecraft.com) |  | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Theseus](https://theseus.us) | GPS Denied Navigation for Drones | robotics | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/theseus/jobs) |
| **new** | [Theseus Robotics](https://theseus.bot/) | Humanoids to restock retail shelves & pick orders | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Topological](https://www.topological.com) | Physics-based foundation models for CAD optimization. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Tornyol](https://tornyol.com/) | We build micro-drones that kill mosquitoes. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Trexo Robotics](http://trexorobotics.com) | Exoskeletons to help people walk, starting with children | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [twentyfour26](https://twentyfour26.com/) | On Demand CNC Prototyping | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Twolabs](https://twolabs.ai) | RL environments for underexplored domains. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Ultrasonium](https://ultrasonium.com/) | Metal manufacturing, faster, cheaper, and more versatile. | robotics | no board linked from its site (8 pages) or found under its name |
| **new** | [UXDuck](https://uxduck.com) | Build better drones. Run better missions. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Velontra](https://www.velontra.com/) | Hypersonic space plane that can take-off from any location and weather | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Vendra](https://vendra.io/) | Custom Parts, Manufactured in America 🇺🇸 | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/vendra/jobs) |
| **new** | [Vernius Systems, Inc.](https://www.vernius.systems) | Mass-deployable radars for air defense | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/vernius-systems-inc/jobs) |
| **new** | [Voltair](https://voltairlabs.com/) | Autonomous Drones for Earth Observation | robotics | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/voltair/jobs) |
| **new** | [Waddle Labs](https://www.waddlelabs.ai/) | LLMs that control robots | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/waddle-labs/jobs) |
| **new** | [Well Principled](https://wellprincipled.com) | The neural engine for autonomous robots | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Yondu](https://yondu.ai/) | Robots to Automate Fulfillment | robotics | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/yondu/jobs) |
| **new** | [Yoshi Mobility](https://www.yoshimobility.com) | Making car ownership and management frictionless. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [Yummy Future](https://yummy-future.com) | We build robotic workforces for the food & beverage industry. | robotics | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/yummy-future/jobs) |
| **new** | [Zeitview](https://www.zeitview.com/) | Inspection software for renewable energy & sustainable infrastructure | robotics | uses Trakstar Hire, which phlux has no reader for |
| **new** | [Zeon Systems](https://www.zeonsystems.ai/) | AI-powered robotics for scientific lab automation. | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [ZETA SURGICAL](http://zetasurgical.com) | Next-Generation Surgical Navigation and Robotics | robotics | no board linked from its site (7 pages) or found under its name |
| **new** | [1849 bio](https://www.1849.bio) | Engineering microbes for miners to unlock billions in trapped metal | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [83 Sciences](https://83sciences.ai) | AI-native materials discovery powered by unpublished experimental data | adjacent | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/83-sciences/jobs) |
| **new** | [Advano](http://www.advano.io) | Advano is a battery technology company that improve the longevity of… | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Aerogen Systems](https://www.aerogensystems.com/) | Modernizing Chip Manufacturing Infrastructure | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Airhart Aeronautics](https://www.airhartaero.com/) | Airplanes anyone can fly | adjacent | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/airhart-aeronautics/jobs) |
| **new** | [AirMyne](http://www.airmyne.com) | Building systems to remove carbon dioxide from air at industrial scale | adjacent | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/airmyne/jobs) |
| **new** | [Airthium](http://www.airthium.com) | Decarbonized heat and power cheaper than fossil fuels | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Alba Orbital](https://www.albaorbital.com) | We make satellites to image everywhere on Earth, every 15 minutes | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [AmpUp](https://ampup.io) | We make EV charging as simple and reliable as LED lights | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Andson Biotech](http://www.andsonbiotech.com) | Empowering Mass Spec for Biotech and Beyond | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Applied Electrodynamics, Inc.](https://www.ae-dyn.com/) | A new kind of camera that can see through walls. | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Ares Industries](https://aresindustries.com) | Building low-cost cruise missiles | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Arlo Industries](https://arlo1.com/) | Track drones and missiles without radars - Accurate, Passive, Scalable | adjacent | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/arlo-industries/jobs) |
| **new** | [Array Labs](https://www.arraylabs.io/) | We're building satellites to create a real-time 3D map of the world. | adjacent | lever 'arraylabs' could not be read: 404 Client Error: Not Found for url: https://api.lever.co/v0/postings/arraylabs?mode=json · hiring on [YC](https://www.ycombinator.com/companies/array-labs/jobs) |
| **new** | [Atomarine](https://atomarine.co) | Floating nuclear powered data centers at sea. | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Auricle](https://auricle.com) | Neurostimulation implant to restore hearing & speech understanding | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [AxionOrbital Space](https://axionorbital.space/) | Foundation models for 24/7 Earth Observation | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Basalt](https://basalt.space/) | Constellations as a Service | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Baud](https://baudlabs.ai) | AI chips for ultra-fast training and inference | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Beyond Aero](https://www.beyond-aero.com/) | First electric business aircraft designed for hydrogen propulsion | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Biocartesian](https://www.biocartesian.com) | Converting biology into digital molecular maps | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Cactus Compute](https://www.cactuscompute.com/) | Automation Foundation Models For Tiny Devices | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Care Weather](https://www.careweather.com) | The highest-accuracy global weather data from low-cost flat satellites | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Cascade Space](https://cascadespace.com) | Commercial alternative to the Deep Space Network | adjacent | no board linked from its site (8 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/cascade-space/jobs) |
| **new** | [Conductor Quantum](https://www.conductorquantum.com) | AI that operates quantum computers for scientific discovery | adjacent | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/conductor-quantum/jobs) |
| **new** | [Consus](https://www.consus.io) | The fastest and cheapest way to use AI with ITAR or CUI data. | adjacent | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/consus/jobs) |
| **new** | [Coulomb AI](https://coulomb.ai/) | Battery Observability Platform for Electric Vehicles | adjacent | no board linked from its site (8 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/coulomb-ai/jobs) |
| **new** | [Daqstra](https://www.daqstra.com) | AI-native test infrastructure layer for hardware companies | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Dipole Labs](https://dipolelabs.com/) | AI-controlled optical switching for AI clusters | adjacent | no board linked from its site (8 pages) or found under its name |
| **new** | [Dispatch](https://dispatch.space/) | Satellites for Manufacturing in Space | adjacent | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/dispatch/jobs) |
| **new** | [Ekho Labs](https://ekholabs.com/) | World Model for Freight | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Emobi](https://www.emobi.ai) | A single point integration for secure and automated EV charging. | adjacent | site unreachable: https://www.emobi.ai/ answered 403 |
| **new** | [Enhanced Radar](https://www.enhancedradar.com/) | AI systems for aviation | adjacent | no board linked from its site (8 pages) or found under its name |
| **new** | [Enlightra](https://www.enlightra.com/) | Multicolor lasers for ultrafast data transmission | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [EPIC AEROSPACE](http://epic-aerospace.com) | Last-mile delivery for satellites. | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Ethos Space Resources](https://ethos-space.com) | We make silicon on the Moon, to power everything in space. | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Exosat](https://www.exosat.com) | Building a neutral, sovereign alternative to Starlink | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [F4 Industries](https://f4.dev/) | The GD&T Analysis Platform for Engineering Drawings | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Frontier Computing](https://frontier.site) | Frontier grows scalable biological brains as an ML training substrate | adjacent | no board linked from its site (8 pages) or found under its name |
| **new** | [Galactic Resource Utilization Space, Inc. (GRU Space)](https://gru.space) | Moon Hotel -> The Intergalactic Construction Company of Earth | adjacent | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/galactic-resource-utilization-space-inc-gru-space/jobs) |
| **new** | [GBatteries](https://www.gbatteries.com) | Enabling li-ion batteries to charge ultra fast without compromising… | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Godela](http://godela.ai) | AI Physics Engine to replace simulations and prototypes | adjacent | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/godela/jobs) |
| **new** | [Greywing](https://grey-wing.com/) | The Operating System for Maritime | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [GroundControl](https://rungroundcontrol.com/) | Vertical AI for highly-regulated manufacturing | adjacent | rippling 'groundcontrol' could not be read: 404 Client Error: Not Found for url: https://ats.rippling.com/api/v2/board/groundcontrol/jobs?page=0&pageSize=100 · hiring on [YC](https://www.ycombinator.com/companies/groundcontrol/jobs) |
| **new** | [HABU](https://buildhabu.com) | Like Crosby, but for real estate development | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [HEO Robotics](https://www.heo-robotics.com/) | We visually monitor space objects for governments and defense | adjacent | no board linked from its site (8 pages) or found under its name |
| **new** | [Humane Genomics](https://humanegenomics.com) | A platform to make artificial viruses as cancer therapeutics. | adjacent | no board linked from its site (8 pages) or found under its name |
| **new** | [Induction Labs](https://inductionlabs.com) | Building intellectually curious AI | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Instinct Space](https://www.instinct-space.com/) | Building lunar landers | adjacent | no board linked from its site (8 pages) or found under its name |
| **new** | [Integrated Reasoning](https://integrated-reasoning.com) | Faster processors for solving NP-complete problems | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Keres](https://www.keresaero.com/) | Kill the drone, keep the jet. Reusable unmanned interceptors. | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Kilobaser](https://www.kilobaser.com) | Desktop DNA Printer. The Nespresso Machine for DNA. | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Liquid Energy](https://www.liquidenergy.world) | Self contained solar-powered AI inference modules: the NanoDC | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Meteoric](https://meteoric.earth/) | Drones that clear clouds over solar farms and weaken hurricanes | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Navier AI](http://navier.ai) (tracked *Navier* is a similar name) | Agent-Driven Engineering | adjacent | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/navier-ai/jobs) |
| **new** | [Ndea](https://ndea.com) | Building AGI that can innovate. | adjacent | no board linked from its site (8 pages) or found under its name |
| **new** | [NearWave](http://nearwave.co) | Helping physicians select the right therapy for breast cancer patients | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [NetworkOcean](https://networkocean.io/) | We build floating solar data centers | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [NODI Energy](https://www.nodienergy.com) | Distributed energy infrastructure unlocking grid power to data centers | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Olympian Motors](https://olympianmotors.com/) | Next-generation, modular electric vehicles | adjacent | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/olympian-motors/jobs) |
| **new** | [Optifye.ai](https://www.optifye.ai) | AI performance monitoring for factory workers | adjacent | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/optifye-ai/jobs) |
| **new** | [Orca Aerospace](https://orcaaerospace.com/) | AI spacecraft operators that lives onboard the vehicle | adjacent | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/orca-aerospace/jobs) |
| **new** | [Palitronica Inc](https://palitronica.com) | Detect cyber attacks on critical physical infrastructure | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Photonium](https://www.photoniumoptics.com/) | AI-Powered Optical Consulting & Software | adjacent | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/photonium/jobs) |
| **new** | [Piris Labs](https://pirislabs.io/) | The Networking Layer of AI | adjacent | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/pirislabs/jobs) |
| **new** | [Potion](https://www.potion.ai) | AI for product formulation | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Praxis Robotics](https://www.praxisrobotics.io) | Turns real businesses into robotics data vendors | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Prime Lightworks](http://www.primelightworks.com) | Prime Lightworks Inc. manufactures electric propulsion systems for… | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [RATLOG](https://www.ratlog.space/) | Reusable heavy-lift rockets | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Reditus Space](https://www.reditus.space/) | Reusable Satellites | adjacent | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/reditus-space/jobs) |
| **new** | [Revoy](https://www.revoy.com) | Make diesel semi trucks hybrid-electric | adjacent | no board linked from its site (8 pages) or found under its name |
| **new** | [rex.fit](https://www.rex.fit) | Automating nutrition tracking. | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Rise Reforming](https://rise-reforming.com/home) | We turn waste gases into supply-secure chemicals | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Saccade](https://saccade.health) | World's Earliest Test for Alzheimer's Biomarkers | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [SigmanticAI](https://www.sigmanticai.com) | The Cursor for Chip Design - Delivering Silicon-Ready Chip Designs… | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [SiPhox Health](https://www.siphoxhealth.com) | At-Home health monitoring with silicon photonic chips for data centers | adjacent | no board linked from its site (8 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/siphox-health/jobs) |
| **new** | [Skymerse](https://skymerse.com) | Autopilot for Flight Operations | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [spotLESS Materials](https://www.industry.spotlessmaterials.com) | Repellent coatings without PFAS | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Starcloud](https://www.starcloud.com/) | Data centers in space | adjacent | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/starcloud/jobs) |
| **new** | [Statiq.](https://statiq.in/) | India's Largest EV charging network | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Steinmetz](https://steinmetzmotors.com/) | Next-Generation Power Electronics | adjacent | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/steinmetz/jobs) |
| **new** | [Stralis Aircraft](https://stralis.aero/) | Emission free hydrogen electric aircraft | adjacent | no board linked from its site (8 pages) or found under its name |
| **new** | [SubVysion](https://subvysion.com) | Autonomous rovers to make the ‘Google Maps’ of underground utilities | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Tesseract](http://tesseract.space) | Tesseract builds better thrusters for modern satellites | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [The Subvocal Company](https://subvocal.company) | Talk to your computer without talking | adjacent | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/the-subvocal-company/jobs) |
| **new** | [TransAstra Corporation](https://www.transastra.com) | Orbital logistics: Unleashing space industry, from Earth to asteroids | adjacent | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/transastra-corporation/jobs) |
| **new** | [Ukama](http://www.ukama.com) | Empowering anyone to build cellular network | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Ultralight](https://ultralig.ht) | Universal, Pure-GPU HTML Renderer | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [VedaBio](https://www.vedabio.com) | CRISPR powered Diagnostics with results in minutes. | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Vena Vitals](http://venavitals.com) | A small sticker that monitors blood pressure continuously | adjacent | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/vena-vitals/jobs) |
| **new** | [Viraj Aero](https://www.viraj-aero.com/) | Next generation gas turbines for data centers & aviation | adjacent | no board linked from its site (8 pages) or found under its name |
| **new** | [Visibl Semiconductors](https://visiblsemi.com) | Custom silicon for power electronics | adjacent | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/visibl-semiconductors/jobs) |
| **new** | [Vorelios](https://vorelios.com) | Solving engineering, then using it to solve everything else | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Wright Electric](http://www.weflywright.com) | Boeing for electric planes | adjacent | no board linked from its site (7 pages) or found under its name · hiring on [YC](https://www.ycombinator.com/companies/wright-electric/jobs) |
| **new** | [Wyvern](http://www.wyvern.space) | High-res hyperspectral pictures of Earth from space | adjacent | no board linked from its site (8 pages) or found under its name |
| **new** | [Zelos Cloud](https://zeloscloud.io) | The Data Platform for Mission‑Critical Systems | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Zephyr Fusion](https://www.zephyrfusion.com) | Powering tomorrow's industrial revolution in space | adjacent | no board linked from its site (7 pages) or found under its name |
| **new** | [Zettascale Computing](https://zscc.ai) | Chips for frontier AI | adjacent | uses YC Work at a Startup, which phlux has no reader for · hiring on [YC](https://www.ycombinator.com/companies/zettascale-computing/jobs) |
| **new** | [Zitara Technologies, Inc.](https://zitara.com) | Predictive battery management software for electrified fleets | adjacent | no board linked from its site (8 pages) or found under its name |

## Already tracked (4)

Skipped because they match a `companies.csv` row.
These are in `companies.csv` but not in `lists/robotics.json`, so the bot never reads them:

- Stoke Space (row Stoke Space: same name, 'Stoke Space')

<details><summary>All skipped candidates</summary>

- Gecko Robotics → Gecko Robotics (same name, 'Gecko Robotics')
- May Mobility → May Mobility (same name, 'May Mobility')
- Relativity Space → Relativity (same name, 'Relativity')
- Stoke Space → Stoke Space (same name, 'Stoke Space')

</details>
