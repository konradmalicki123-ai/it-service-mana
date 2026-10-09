# Agent policy

Each denial is a blast-radius decision for an agent working in this repository.

- Bash: a shell in this tree can reach the Docker socket and the network, so an agent could rebuild images or call out while the grader expects a closed build.
- WebFetch: fetching an arbitrary URL would let an agent pull another student's repository or a metrics.json that is useless on the graded log and is not this submission.
- WebSearch: search is the same door as fetch, and the laboratory asks for the published rulebook rather than a page that paraphrases it.
