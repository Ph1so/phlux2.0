# Company shortlist

Robotics and robotics-adjacent companies that phlux doesn't track yet, kept here to decide on later.
Nothing in this file is scraped. Snapshot from the discovery run on 2026-11-01; counts were live then.
The weekly discovery report, [README.md](README.md), has current numbers and newly found companies;
it never touches this file.

**Added to tracking on 2026-11-01:** Beyond Reach Labs, Pyka, Relling, Icarus, Weave Robotics (its real board is
Dover, not the same-named Greenhouse board listed here before), Tuesday Labs and Boost Robotics.

**To add a company:** paste its row into `companies.csv`, then add its name to `lists/robotics.json`
(the bot only scrapes companies in that list). While `seed_new_companies` in `storage.json` is false,
its first scrape emails every internship it has open; set it to true first for a silent start.

## Robotics, internships open (15)

| Company | What they do | Internships / postings | Job board |
| --- | --- | --- | --- |
| [Spaceium Inc](https://spaceium.com) | In-Space Refueling | 5 / 12 | [greenhouse](https://job-boards.greenhouse.io/spaceium) |
| [AstroForge](https://www.astroforge.io/) | We Mine Asteroids | 4 / 15 | [gem](https://jobs.gem.com/astroforge-io) |
| [Multiply Labs](http://multiplylabs.com/) | Robotic production capacity for the pharma manufacturing industry | 3 / 11 | [lever](https://jobs.lever.co/multiplylabs) |
| [Nox Metals](https://noxmetals.co/) | Supplying America's Industrial Base | 2 / 37 | [ashby](https://jobs.ashbyhq.com/nox-metals) |
| [Revise Robotics](https://www.reviserobotics.com/) | Automating refurbishment of $1T in consumer electronics | 2 / 2 | [ashby](https://jobs.ashbyhq.com/reviserobotics) |
| [Brumby](https://brumby.com) | Robot Cowboys that Herd Cattle with AI Drones | 1 / 4 | [ashby](https://jobs.ashbyhq.com/brumby) |
| [Fleetzero](https://www.fleetzero.com) | Making all ships robots. | 1 / 2 | [lever](https://jobs.lever.co/fleetzero) |
| [Human Archive](https://www.humanarchive.ai/) | Physical AI data lab | 1 / 21 | [ashby](https://jobs.ashbyhq.com/humanarchive) |
| [Innate](https://innate.bot) | Personal AI Robots | 1 / 3 | [ashby](https://jobs.ashbyhq.com/innate) |
| [One Robot](https://www.onerobot.io/) | World models for robot evals and training. | 1 / 3 | [ashby](https://jobs.ashbyhq.com/onerobot) |
| [Overview](https://overview.ai) | Reshaping industrial quality with AI, hardware, and software | 1 / 62 | [ashby](https://jobs.ashbyhq.com/overview) |
| [Pivot Robotics](https://pivotrobotics.com) | AI for Robot Arms in Factories | 1 / 5 | [ashby](https://jobs.ashbyhq.com/pivotrobotics) |
| [Shinkei Systems](http://www.shinkei.systems) | Robots for longer-lasting, better-tasting fish at scale. | 1 / 16 | [kula](https://careers.kula.ai/shinkei) |
| [Sorting Robotics](https://www.sortingrobotics.com/) | We create automation technology for the cannabis industry. | 1 / 8 | [workable](https://apply.workable.com/sorting-robotics/) |
| [Verne Robotics](https://vernerobotics.com/) | AI models that teach robots new skills in hours | 1 / 6 | [ashby](https://jobs.ashbyhq.com/Verne%20Robotics) |

<details><summary>Rows for <code>companies.csv</code></summary>

```csv
Spaceium,https://job-boards.greenhouse.io/spaceium,@greenhouse
AstroForge,https://jobs.gem.com/astroforge-io,@gem
Multiply Labs,https://jobs.lever.co/multiplylabs,@lever
Nox Metals,https://jobs.ashbyhq.com/nox-metals,@ashby
Revise Robotics,https://jobs.ashbyhq.com/reviserobotics,@ashby
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
```

</details>

## Adjacent: space, aerospace, energy, internships open (12)

| Company | What they do | Internships / postings | Job board |
| --- | --- | --- | --- |
| [Astranis](http://www.astranis.com) | Advanced satellites for high orbits. | 92 / 185 | [greenhouse](https://job-boards.greenhouse.io/astranis) |
| [HyLight](https://www.hylight.aero/) | Unmanned airships for inspecting our critical assets | 8 / 23 | [dover](https://app.dover.com/HyLight/careers/07e7aff2-18e8-4518-8d08-b6a6b165ea97) |
| [Inversion Space](https://www.inversionspace.com/) | Turning space into a transportation layer for Earth | 7 / 90 | [greenhouse](https://job-boards.greenhouse.io/inversionspace) |
| [Helion Energy](http://helionenergy.com) | Building the world's first fusion power plant | 4 / 63 | [ashby](https://jobs.ashbyhq.com/helion) |
| [Odys Aviation](https://www.odysaviation.com/) | Vertical takeoff and landing aircraft for major airlines | 3 / 14 | [ashby](https://jobs.ashbyhq.com/odys-aviation) |
| [General Astronautics](https://generalastro.com/) | Superintelligent space Robots | 2 / 5 | [ashby](https://jobs.ashbyhq.com/generalastronautics) |
| [H3X Technologies](http://h3x.tech/) | The lightest electric aircraft motors in the world. | 2 / 4 | [ashby](https://jobs.ashbyhq.com/h3x-technologies) |
| [Wardstone](https://www.wardstone.us) | The Modular Interceptor Platform | 2 / 19 | [gem](https://jobs.gem.com/wardstone-space) |
| [Apolink](https://apolink.space) | 24/7 satellite connectivity in low Earth orbit | 1 / 2 | [ashby](https://jobs.ashbyhq.com/apolink) |
| [Boom](https://boomsupersonic.com/) | Economically and environmentally sustainable supersonic travel | 1 / 29 | [rippling](https://ats.rippling.com/boom-supersonic/jobs) |
| [Orbital Operations](https://www.orbitalops.tech/) | High Thrust Space Vehicles for Satellite Defense | 1 / 5 | [greenhouse](https://job-boards.greenhouse.io/orbitaloperations) |
| [Singularity](https://www.singularityus.com/) | Building and Protecting an Exciting Future | 1 / 28 | [rippling](https://ats.rippling.com/singularity-defense/jobs) |

<details><summary>Rows for <code>companies.csv</code></summary>

```csv
Astranis,https://job-boards.greenhouse.io/astranis,@greenhouse->FILTER:intern
HyLight,https://app.dover.com/HyLight/careers/07e7aff2-18e8-4518-8d08-b6a6b165ea97,@dover
Inversion Space,https://job-boards.greenhouse.io/inversionspace,@greenhouse->FILTER:intern
Helion Energy,https://jobs.ashbyhq.com/helion,@ashby->FILTER:intern
Odys Aviation,https://jobs.ashbyhq.com/odys-aviation,@ashby
General Astronautics,https://jobs.ashbyhq.com/generalastronautics,@ashby
H3X Technologies,https://jobs.ashbyhq.com/h3x-technologies,@ashby
Wardstone,https://jobs.gem.com/wardstone-space,@gem
Apolink,https://jobs.ashbyhq.com/apolink,@ashby
Boom,https://ats.rippling.com/boom-supersonic/jobs,@rippling
Orbital Operations,https://job-boards.greenhouse.io/orbitaloperations,@greenhouse
Singularity,https://ats.rippling.com/singularity-defense/jobs,@rippling
```

</details>

## Robotics, no internships open (21)

Boards phlux can read; worth adding before their next hiring season.

| Company | What they do | Postings | Job board |
| --- | --- | --- | --- |
| [Aerones](http://www.aerones.com) | Robotics for wind turbine maintenance. | 22 | [workable](https://apply.workable.com/aerones/) |
| [Andromeda Surgical](http://www.andromedasurgical.com) | Autonomous surgical robots | 3 | [ashby](https://jobs.ashbyhq.com/andromedasurgical) |
| [AON3D](https://www.aon3d.com) | Additive Manufacturing with advanced materials | 2 | [greenhouse](https://job-boards.greenhouse.io/aon3d-fr) |
| [Atum Works](https://atum.works/) | Gigascale Nanomanufacturing | 3 | [ashby](https://jobs.ashbyhq.com/atumworks) |
| [Azalea Robotics Corporation](https://azalearobotics.com/) | Automating airport baggage handling with robots. | 1 | [dover](https://app.dover.com/jobs/azalearobotics) |
| [Charge Robotics](https://chargerobotics.com/) | Robots that build solar farms | 13 | [ashby](https://jobs.ashbyhq.com/charge-robotics) |
| [CircuitHub](https://circuithub.com) | On-Demand Electronics Manufacturing | 10 | [ashby](https://jobs.ashbyhq.com/circuithub) |
| [Corvus Robotics](https://www.corvus-robotics.com) | Autonomous drones to help warehouses scan inventory. | 8 | [ashby](https://jobs.ashbyhq.com/corvus-robotics) |
| [Cosmic Robotics](https://www.cosmicrobotics.com/) | Autonomous construction on Earth and beyond | 5 | [ashby](https://jobs.ashbyhq.com/cosmic-robotics) |
| [Duranium](https://www.duranium.co/) | Reshoring critical metal production | 1 | [dover](https://app.dover.com/jobs/duranium) |
| [Encord](https://encord.com) | The data layer for physical AI | 35 | [ashby](https://jobs.ashbyhq.com/encord) |
| [JITX](http://www.jitx.com) | Automatic circuit board design. | 2 | [lever](https://jobs.lever.co/jitxinc) |
| [Loombotic](https://www.loombotic.com) | Wire Harnesses in as little as 7 days | 8 | [dover](https://app.dover.com/jobs/loombotic) |
| [Lucid Bots](https://lucidbots.com/) | We build robots for dull, dirty, and dangerous jobs. | 1 | [ashby](https://jobs.ashbyhq.com/lucidbots) |
| [Neuron Industries](https://neuronindustries.com) | Industrial Controllers built for AI | 9 | [gem](https://jobs.gem.com/neuron) |
| [Paladin](http://paladindrones.io) | We deploy autonomous drones to 911 calls. Our software gives first… | 1 | [jazzhr](https://paladindrones.applytojob.com/apply) |
| [Skyways](http://skyways.com) | Creating a new form of air transportation to advance our civilization | 20 | [lever](https://jobs.lever.co/skyways) |
| [Tekton Dynamics](https://www.tekton-dynamics.com) | AI control layer for welding robots | 2 | [ashby](https://jobs.ashbyhq.com/tekton-dynamics) |
| [Ultra](https://ultra.tech) | Practical, general-purpose robots for repetitive industrial tasks | 18 | [gem](https://jobs.gem.com/ultra) |
| [Volta Labs, Inc.](http://voltalabs.com) | Unlocking the utility of genomics for the world. | 3 | [lever](https://jobs.lever.co/voltalabs) |
| [Vorticity](http://vorticity.xyz/) | The Fastest Scientific Computing Platform on the Planet | 1 | [ashby](https://jobs.ashbyhq.com/vorticity) |

<details><summary>Rows for <code>companies.csv</code></summary>

```csv
Aerones,https://apply.workable.com/aerones/,@workable
Andromeda Surgical,https://jobs.ashbyhq.com/andromedasurgical,@ashby
AON3D,https://job-boards.greenhouse.io/aon3d-fr,@greenhouse
Atum Works,https://jobs.ashbyhq.com/atumworks,@ashby
Azalea Robotics Corporation,https://app.dover.com/jobs/azalearobotics,@dover
Charge Robotics,https://jobs.ashbyhq.com/charge-robotics,@ashby
CircuitHub,https://jobs.ashbyhq.com/circuithub,@ashby
Corvus Robotics,https://jobs.ashbyhq.com/corvus-robotics,@ashby
Cosmic Robotics,https://jobs.ashbyhq.com/cosmic-robotics,@ashby
Duranium,https://app.dover.com/jobs/duranium,@dover
Encord,https://jobs.ashbyhq.com/encord,@ashby
JITX,https://jobs.lever.co/jitxinc,@lever
Loombotic,https://app.dover.com/jobs/loombotic,@dover
Lucid Bots,https://jobs.ashbyhq.com/lucidbots,@ashby
Neuron Industries,https://jobs.gem.com/neuron,@gem
Paladin,https://paladindrones.applytojob.com/apply,@jazzhr
Skyways,https://jobs.lever.co/skyways,@lever
Tekton Dynamics,https://jobs.ashbyhq.com/tekton-dynamics,@ashby
Ultra,https://jobs.gem.com/ultra,@gem
Volta Labs,https://jobs.lever.co/voltalabs,@lever
Vorticity,https://jobs.ashbyhq.com/vorticity,@ashby
```

</details>

## Adjacent, no internships open (15)

| Company | What they do | Postings | Job board |
| --- | --- | --- | --- |
| [Albedo](https://albedo.com) | Full-stack VLEO satellite missions | 5 | [greenhouse](https://job-boards.greenhouse.io/albedo) |
| [Astro Mechanica](https://astromecha.co/) | Supersonics for the new Jet Age | 40 | [ashby](https://jobs.ashbyhq.com/Astro-Mechanica) |
| [Curri](http://www.curri.com) | Construction & industrial logistics platform. | 24 | [ashby](https://jobs.ashbyhq.com/curri) |
| [Epsilon3](https://www.epsilon3.io/) | AI-Powered ERP, MES, and Test Software for Complex Operations | 4 | [lever](https://jobs.lever.co/epsilon3) |
| [Farcast](https://www.farcast.com/) | We build advanced satcom user terminals | 3 | [lever](https://jobs.lever.co/Farcast) |
| [Heart Aerospace](http://www.heartaerospace.com) | Heart makes electric airplanes with an all-electric range of 250 miles | 4 | [greenhouse](https://job-boards.greenhouse.io/heartaerospace) |
| [Hubble Network](https://hubble.com) | Bluetooth to Space | 17 | [greenhouse](https://job-boards.greenhouse.io/hubblenetwork) |
| [Inflection Space Systems](https://inflection-space.com/) | Hyperscaling space manufacturing | 6 | [rippling](https://ats.rippling.com/inflection-space/jobs) |
| [Luminate](http://www.luminatemed.com) | We make cancer care at home possible. | 7 | [bamboohr](https://luminatemedical.bamboohr.com/careers) |
| [Maritime Fusion](https://maritimefusion.com) | Fusion reactors for ships | 4 | [gusto](https://jobs.gusto.com/boards/maritime-fusion-34d86452-e58d-44d8-86b9-39b654807910) |
| [Meticulous](https://www.meticulous.ai) | Automated e2e screenshot testing without writing or maintaining tests | 6 | [ashby](https://jobs.ashbyhq.com/meticulous) |
| [Mindstate Design Labs](http://mindstate.design) | Programmable biology company for psychoactive effect design | 1 | [rippling](https://ats.rippling.com/mindstate-design-labs/jobs) |
| [Quindar](https://www.quindar.space) | Datadog for Space | 19 | [ashby](https://jobs.ashbyhq.com/quindar) |
| [REGENT](http://regentcraft.com) | All-electric seagliders for fast, affordable regional transportation | 34 | [ashby](https://jobs.ashbyhq.com/regent) |
| [Turion Space](https://turionspace.com/) | Moving Things Around in Space, Imaging Space Objects When We're Not | 15 | [ashby](https://jobs.ashbyhq.com/turion-space) |

<details><summary>Rows for <code>companies.csv</code></summary>

```csv
Albedo,https://job-boards.greenhouse.io/albedo,@greenhouse
Astro Mechanica,https://jobs.ashbyhq.com/Astro-Mechanica,@ashby
Curri,https://jobs.ashbyhq.com/curri,@ashby
Epsilon3,https://jobs.lever.co/epsilon3,@lever
Farcast,https://jobs.lever.co/Farcast,@lever
Heart Aerospace,https://job-boards.greenhouse.io/heartaerospace,@greenhouse
Hubble Network,https://job-boards.greenhouse.io/hubblenetwork,@greenhouse
Inflection Space Systems,https://ats.rippling.com/inflection-space/jobs,@rippling
Luminate,https://luminatemedical.bamboohr.com/careers,@bamboohr
Maritime Fusion,https://jobs.gusto.com/boards/maritime-fusion-34d86452-e58d-44d8-86b9-39b654807910,@gusto
Meticulous,https://jobs.ashbyhq.com/meticulous,@ashby
Mindstate Design Labs,https://ats.rippling.com/mindstate-design-labs/jobs,@rippling
Quindar,https://jobs.ashbyhq.com/quindar,@ashby
REGENT,https://jobs.ashbyhq.com/regent,@ashby
Turion Space,https://jobs.ashbyhq.com/turion-space,@ashby
```

</details>

## Check before adding (2)

These boards share the company's name but nothing confirmed it is the same company.

| Company | What they do | Postings | Job board |
| --- | --- | --- | --- |
| [Preload](https://preload.ai) | Sensorimotor context for physical AI | 9 | [greenhouse](https://job-boards.greenhouse.io/preload) |
| [Remora](https://www.remoracarbon.com) | Modular carbon capture | 9 | [greenhouse](https://job-boards.greenhouse.io/remoracarbon) |

<details><summary>Rows for <code>companies.csv</code></summary>

```csv
Preload,https://job-boards.greenhouse.io/preload,@greenhouse
Remora,https://job-boards.greenhouse.io/remoracarbon,@greenhouse
```

</details>
