# Capstone reflection

Signal Desk turns an ambiguous inbox into a reviewable work queue for a small creative studio. The implementation joined a locally trained logistic model, evidence-based score explanation, four-state tool lifecycle, and streaming assistant response. The score is a synthetic-data sorting signal, not a calibrated prediction; a person remains responsible for deciding whether and how to reply.

The most useful learning was to keep feature extraction, tool validation, and UI display separate. A model output can look certain even when its data is weak, so the interface now shows supporting signals, cautions, and open questions. The comma-separated budget mismatch was a concrete reminder to test structured inputs, not just prose descriptions. I also practiced focus trapping and restoration, streamed event parsing and cancellation, reduced-motion graphics, lazy client chunks, and error recovery.

The main limitation is evidence maturity. The app uses only invented records and has no calibration study, actual studio-user feedback, deployed preview, Lighthouse report, WAVE report, or mentor review. Before calling this production-ready, I would test with consented studio intake examples, make the training set representative, audit false positives and missed leads, and replace the in-memory rate limit with a shared service. The next release decision should depend on those findings, not on the score looking polished.

The public repository and current capstone evidence have been submitted to FlyRank. The hosted preview and production smoke check are still missing because no deployment host is connected. The portal shows the capstone as Submitted, not Accepted; mentor review is pending.
