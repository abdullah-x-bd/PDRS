# Permanent release steps

1. Merge the reviewed PDRS and FinSpace Phase 10–18 pull requests.
2. Create an immutable paper tag on the exact PDRS merge commit.
3. Attach the final PDF, arXiv source, raw evidence, environment metadata, mutation reports, and checksums.
4. Enable the PDRS repository in the repository owner's Zenodo GitHub integration.
5. Create the GitHub release and wait for Zenodo to mint a DOI.
6. Verify that the DOI resolves to the exact release.
7. Insert the returned DOI into the manifest and manuscript, then rebuild.

No guessed, reserved, or draft DOI satisfies the completion gate.
