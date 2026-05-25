# FaultForge Paper

LaTeX source for "FaultForge: Symptom-Guided Minimal Fault Recipe Synthesis for Distributed Systems".

## Building

```bash
cd paper
make        # Produces main.pdf
make clean  # Removes build artifacts
```

Requires a TeX Live installation (`texlive-latex-base`, `texlive-latex-extra`, `texlive-fonts-recommended`, `texlive-science`, `texlive-pictures`).

## Structure

- `main.tex` — Complete paper source (single-file for portability)
- `Makefile` — Build automation

## Target Venue

Top-tier systems conference (NSDI / OSDI / ATC / EuroSys).
