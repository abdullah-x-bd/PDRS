# Immutable artifact release steps

Perform these steps only after all three arXiv v2 workflow jobs pass.

1. Merge the reviewed revision branch.
2. Create an annotated Git tag such as `pdrs-paper-v1.0` on the exact merge commit.
3. Create the corresponding GitHub release and attach the successful workflow artifacts.
4. Verify that the repository is enabled in the owner's Zenodo GitHub settings.
5. Wait for Zenodo to archive the release and mint a DOI.
6. Replace the null DOI in `zenodo_metadata.json`, `artifact_manifest.json`, and the manuscript.
7. Recompile the paper and verify that the cited DOI resolves to the exact release.

A pending publisher entry, draft DOI, or guessed DOI is not a completed permanent archive.
