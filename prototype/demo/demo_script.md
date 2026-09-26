# CiteFrontier live presenter flow

This is a live, text-only walkthrough. Start with `prototype/demo/start-demo.ps1`.
Official mode is used by default, so enter the questions manually. Keep the
Validation panel visible when discussing measured results.

Start with **Messy live transcript**. As `umm`, `uh`, and repeated words arrive,
show the real WAIT/tentative transitions. At commit, point to “Understood as” and
the telemetry record containing both raw and cleaned text. The cleanup is a fixed
filler/repetition rule, not an LLM rewrite. The cleaned request must still produce
three independently cited claims.

## 1. Tentative early retrieval

Type the beginning of a venue question without submitting it. Point to the
`WAIT` state while the prefix is unstable, then continue until the stable prefix
causes tentative retrieval. Submit the full question and show that only evidence
validated against the final text enters the answer.

## 2. Three-way multi-intent decomposition

Ask: `For LumaPad S1, what is the warranty period? What receipt opens a repair?
Where is the service desk?` Show the three detected sub-questions, their separately
retrieved extracts, and each citation's source section, hash, and offsets.

## 3. Explicit S1-to-S2 correction

Enter `What is the LumaPad S1 warranty, I meant S2?` Show the “Understood as”
resolution. Explain that the revision invalidates S1 candidates and the committed
answer cites S2 evidence only.

## 4. Selective claim refinement

First ask for warranty duration and repair proof. Then refine only the warranty
request to ask about liquid-damage exclusions. Show that the warranty claim is
replaced while the repair claim keeps its claim ID, text, and citation.

## 5. Presentation suppression

Choose **Show as bullets**. Show that the answer layout changes while search count,
claim evidence, and citations remain unchanged.

## 6. Unsupported-question abstention

Ask whether the product supports telepathy. Show the explicit uncertainty, no
factual claim, and no citation. A nearby product passage is not treated as support.

## 7. G2-G4 disclosure

Open **Validation** and state: “On the frozen 60-case, author-known venue-domain
acceptance set, G2 is 37/40 (92.5%), G3 is 15/15 (100%), and G4 is 90/90 exact
extracts supported with zero fabricated IDs. These are local synthetic results,
not Samsung or blind benchmark results.” Also show 100% trace coverage.

## 8. Organizer conference upload

Open **Organizer corpus**, upload
`prototype/demo/organizer-corpus/Meridian_Hall.md`, and ask a question answered by
that conference file. Open the citation and inspect the exact passage. Reopen
Validation to show that bundled scores are not attributed to the uploaded corpus.
Select **New session** to restore the bundled corpus and demonstrate session
isolation.

## 9. Messy organizer benchmark

Open **Organizer corpus** and upload the two source files under
`prototype/demo/messy-conference/`. Select its `benchmark.json`, then run the
benchmark. Return to the homepage proof strip and show the separate 6/10 result,
100% support among emitted extracts, zero fabricated IDs, and four visible failed
cases. Explain that this is an author-known stress kit containing conflicting
drafts, schedule amendments, similar names, terse ASR-style questions, compound
requests, and an unsupported question. Samsung can replace all three files with
its own corpus and labels; the score is computed only for that session.

Close with: **Fast while tentative. Accountable when committed.**
