# Workout Plugin — Source Index

Vetted methodology and evidence sources behind the templates, progression
engine, and constraint-aware substitution logic in this plugin. Each entry
below is seeded into the `sources` table by `lib/seed.py`.

## acsm_progression_models
- title: Progression Models in Resistance Training for Healthy Adults (ACSM Position Stand)
- author_org: American College of Sports Medicine
- url: https://pubmed.ncbi.nlm.nih.gov/19204579/
- topic_tags: progression, reps-ranges, program-design
- trust_tier: high
- informs: progression.py double-progression model, novice 8-12 rep range defaults

## nsca_foundations_programming
- title: Foundations of Fitness Programming
- author_org: National Strength and Conditioning Association
- url: https://www.nsca.com/contentassets/8323553f698a466a98220b21d9eb9a65/foundationsoffitnessprogramming_201508.pdf
- topic_tags: progressive-overload, program-design
- trust_tier: high
- informs: overall program structure, progressive-overload sequencing

## bodyweightfitness_recommended_routine
- title: Recommended Routine and Strength Training wiki
- author_org: r/bodyweightfitness community (The Fitness Wiki)
- url: https://thefitness.wiki/routines/
- topic_tags: bodyweight, beginner, variation-ladder
- trust_tier: medium
- informs: bodyweight_beginner_3day template, variation-ladder progression model

## autoregulation_rpe_systematic_review
- title: Effects of subjective and objective autoregulation methods for intensity and volume on enhancing maximal strength during resistance-training interventions
- author_org: PeerJ (systematic review)
- url: https://peerj.com/articles/10663/
- topic_tags: rpe, autoregulation, pain-cap
- trust_tier: high
- informs: the user-recorded RPE and pain columns on the printable tracker (v1 has no system-enforced cap in progression.py)

## hsr_vs_eccentric_achilles_rct
- title: Heavy Slow Resistance Versus Eccentric Training as Treatment for Achilles Tendinopathy
- author_org: PubMed (RCT)
- url: https://pubmed.ncbi.nlm.nih.gov/26018970/
- topic_tags: tendinopathy, heavy-slow-resistance, rehab-loading
- trust_tier: high
- informs: constraint-aware loading defaults, tempo conventions (3-0-1 style)

## isometric_eccentric_hsr_systematic_review
- title: Effects of isometric, eccentric, or heavy slow resistance exercises on pain and function in individuals with patellar tendinopathy
- author_org: PubMed (systematic review)
- url: https://pubmed.ncbi.nlm.nih.gov/29972281/
- topic_tags: tendinopathy, isometrics, rehab-loading
- trust_tier: high
- informs: constraint-aware exercise substitution, arm-load/grip flag design

## putting_heavy_into_hsr
- title: Putting "Heavy" into Heavy Slow Resistance
- author_org: PubMed
- url: https://pubmed.ncbi.nlm.nih.gov/35084703/
- topic_tags: heavy-slow-resistance, tempo, load-progression
- trust_tier: medium
- informs: linear and double-progression load-increment defaults

## eccentric_lateral_elbow_tendinopathy_review
- title: The Beneficial Effects of Eccentric Exercise in the Management of Lateral Elbow Tendinopathy
- author_org: PubMed (review)
- url: https://pubmed.ncbi.nlm.nih.gov/34501416/
- topic_tags: tendinopathy, elbow, constraint-aware
- trust_tier: medium
- informs: arm-load / grip constraint flags, arm-free lower-body substitution (sled, belt squat, weighted vest)
