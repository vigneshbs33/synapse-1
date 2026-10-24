# synapse1 physical-flow run "tw" - private evidence record

Produced in the builder's own Linux sandbox (LibreLane 3.0.16, sky130A, ciel PDK version 8afc8346). Not the user's laptop, not native Windows.

Files (sha256 of originals as received):
- synapse1.gds.gz  gzip (-9, no name) of synapse1.gds; gunzip gives the exact original: 13120198 B  37f3654c8f40873693aa5309078e28c7478fa6193651bc2a088111f1d521e18d
- metrics.json  17887 B  5cc45b26d742c4ce28f435a73d1b3bf1a230ee18722fb009d5f49249c95aa2ae (unmodified)
- run-config.json  314 B  6926fd8abe5eafafd888dae7aaafd83563c3b7f6d45df3c6be031ec6ae74df70 (unmodified; uses relative dir:: paths)
- run-design.sdc  465 B  d425ee33b513a59f881018b103917e5d70cc0908844ba6cd8a2576c4ed5449f0 (unmodified)
- signoff-manual.log  685909 B  d161e0f75f1154f1d1df3e52e0ff31129ec49b7de8429b573b7fecbac9fa3f70 (unmodified raw LibreLane stdout of a manual signoff run, builder's Linux, 00:42-00:46 IST; RCX through GDS/render/DRC/LVS warnings; contains the builder's sandbox paths and a harmless first line 'no oauth token found for github.com')
- flow.log  from original 893e1f2ca18ba71a5fe12250bcfa30dab8ee5bea7bc969e7a865052db6868a5c
- warnings.log  from original 285bf0308a4e4f9e14774bf16ebb94edebc150b93d100b35ee98b88738eee1af
  The two logs differ from the originals only by path placeholders: the builder's run directory is now <RUN_ROOT> and the PDK directory is <CIEL_ROOT>.

Recorded results (from metrics): physical DRC 0, LVS 0. Typical corner setup worst slack +0.651 ns. Slow corner at 100 MHz FAILS: -7.794 ns, 1272 endpoints. No fab-readiness claim. Not all corner timing passes.

Scan of all logs found no credentials or keys.

Not verified here: user-laptop run, Windows, full app UI. The raw run.log of the original flow is missing.
The project root (src files, config.json, design.sdc) is unchanged by this commit.
