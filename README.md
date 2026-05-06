## Paper Information

**Title:** The Pragmatic Openness of Open RAN: Navigating the Path from Vendor Lock-in to Interoperability Islands

**Manuscript ID:** 10297

**Submitted to:** IEEE Latin America Transactions

### Authors and Affiliations

**Nima Afraz**  
School of Computer Science, University College Dublin, Ireland  
Email: nima.afraz@ucd.ie

**Mohammad Shojafar**  
5G/6GIC, Institute for Communication Systems, University of Surrey, United Kingdom  
Email: m.shojafar@surrey.ac.uk

**Johann M. Marquez-Barja**  
IDLab, University of Antwerp - imec, Belgium  
Email: johann.marquez-barja@uantwerpen.be

**Hamed Ahmadi**  
Department of Electronic Engineering, University of York, United Kingdom  
Email: hamed.ahmadi@york.ac.uk
This repository contains the code and data used to generate the Open RAN co-occurrence network figure for the paper:


## Repository contents

```text
data/openran_company_edges.csv   Edge-list dataset used to construct the graph
plot_openran_network.py          Python script for generating the network figure
requirements.txt                 Python dependencies
outputs/                         Directory for generated figures
```

## Dataset format

The input CSV is an edge list with three columns:

| Column | Description |
|---|---|
| `CompanyA` | First Open RAN ecosystem actor |
| `CompanyB` | Second Open RAN ecosystem actor |
| `Weight` | Frequency of observed co-occurrence |

Each row represents an observed co-occurrence between two actors in publicly reported Open RAN deployments, trials, pilots, plugfests, or ecosystem collaborations.

## Method summary

The script performs the following steps:

1. Loads and cleans the edge-list dataset.
2. Normalizes selected actor aliases.
3. Removes incomplete, invalid, self-loop, and non-positive-weight records.
4. Aggregates duplicate undirected actor pairs by summing their weights.
5. Builds a weighted undirected NetworkX graph.
6. Applies weighted Louvain community detection.
7. Generates a publication-ready network visualization.

## Installation

Create and activate a Python environment, then install the dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Usage

Run the script from the repository root:

```bash
python plot_openran_network.py
```

This generates:

```text
outputs/pilots.png
```

You can also specify custom input and output paths:

```bash
python plot_openran_network.py --input data/openran_company_edges.csv --output outputs/openran_network.png
```

## Reproducibility notes

The Louvain community detection step uses a fixed random seed for reproducibility. The generated layout may still vary slightly across package versions because graph-layout and label-adjustment algorithms can differ between releases.

## Citation

If you use this code or dataset, please cite the associated paper:

```bibtex
@article{afraz2026pragmatic,
  title={The Pragmatic Openness of Open RAN: Navigating the Path from Vendor Lock-in to Interoperability Islands},
  author={Afraz, Nima and Shojafar, Mohammad and Marquez-Barja, Johann M. and Ahmadi, Hamed},
  journal={IEEE Latin America Transactions},
  year={2026},
  note={Submitted}
}
```

## License

No license has been assigned yet. Add a license file before making the repository public if you want others to reuse the code or data.
