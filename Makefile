PYTHON ?= python3
STORYBOARD ?= storyboard.json

.PHONY: help validate smoke script narration radio-cut keyframes shots music assemble film clean

help:
	@echo "The Heritage Short — Pipeline Targets"
	@echo "  make validate   Validate $(STORYBOARD) against schema/storyboard.schema.json"
	@echo "  make smoke      One-call-per-provider latency test (Gemini text, Gemini TTS, Cloudflare FLUX)"
	@echo "  make narration  Generate Amharic TTS audio per shot"
	@echo "  make radio-cut  Assemble Phase 1 black-screen narration + temp score check"
	@echo "  make keyframes  Generate character/style sheet + per-shot keyframes"
	@echo "  make shots      Generate Wan 2.2 I2V clips (with Ken Burns fallback)"
	@echo "  make music      Generate / select ACE-Step traditional Ethiopian score"
	@echo "  make assemble   Assemble final 9:16 and 16:9 MP4s with subtitles, ducking, loudnorm, end card"
	@echo "  make film       Full reproducible end-to-end run"

validate:
	$(PYTHON) -m pipeline.validate --storyboard $(STORYBOARD)

smoke:
	$(PYTHON) -m pipeline.smoke

script: validate
	$(PYTHON) -m pipeline.script --storyboard $(STORYBOARD)

narration: validate
	$(PYTHON) -m pipeline.narration --storyboard $(STORYBOARD)

radio-cut: narration
	$(PYTHON) -m pipeline.assemble --storyboard $(STORYBOARD) --radio-cut

keyframes: validate
	$(PYTHON) -m pipeline.keyframes --storyboard $(STORYBOARD)

shots: validate
	$(PYTHON) -m pipeline.shots --storyboard $(STORYBOARD)

music: validate
	$(PYTHON) -m pipeline.music --storyboard $(STORYBOARD)

assemble: validate
	$(PYTHON) -m pipeline.assemble --storyboard $(STORYBOARD)

film: validate narration keyframes shots music assemble
	@echo "Done. Outputs in outputs/final/film_9x16.mp4 and outputs/final/film_16x9.mp4"

