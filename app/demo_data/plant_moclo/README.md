# Plant MoClo demo parts

Real GenBank files for the **MoClo Plant Parts Kit** (Weber & Engler et al.),
deposited at Addgene (kit #1000000044) and redistributed here from the
`moclo` Python library registry.

- Upstream: https://github.com/althonos/moclo (`moclo-plant/registry/plant`)
- License: MIT (see `LICENSE.moclo-registry`), Copyright (c) 2018 Martin Larralde
- Primary references:
  - Engler C, et al. (2014) A Golden Gate modular cloning toolbox for plants.
    ACS Synth Biol 3(11):839-843. doi:10.1021/sb4001504
  - Weber E, et al. (2011) A modular cloning system for standardized assembly of
    multigene constructs. PLoS ONE 6(2):e16765.

Each file is a full Level 0 acceptor plasmid: the part (promoter, CDS,
terminator, ...) sits between two convergent BsaI sites with the standard MoClo
fusion overhangs (GGAG, AATG, GCTT, CGCT, ...). The app ingests them with
`parse_part_genbank`, which digests the BsaI sites to recover the part sequence
and its overhangs.

The two acceptor vectors used by the demo (Level 1 BsaI, Level 2 BpiI) are
generated at seed time by `restriction_sites.build_moclo_acceptor`, since the
Plant kit acceptor vectors are not part of this parts registry.
