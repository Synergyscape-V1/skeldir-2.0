# Contracts Tooling Notes

- undle.sh is the authoritative bundling entrypoint for Contract Artifacts CI.
- Placeholder scripts such as uild_docs.sh and alidate_docs.py live here so Contract Artifacts CI is triggered whenever we touch contract tooling.
- Contract Enforcement now downloads the contract-bundles artifact that Contract Artifacts CI produces, so keeping these utilities under scripts/contracts/ ensures both workflows stay in sync.
