# MoniSenForest

MoniSenForest is a tool for handling the tree census data and litterfall data of the Monitoring Sites 1000 Project (also called as "Moni-Sen").

## Overview

MoniSenForest has been developed to assist data collectors in checking data and provide an easy-to-use data preprocessing methods for people who work with data.

Currently, MoniSenForest implements functions such as data cleaning and translation of species names from Japanese names to scientific names. In future updates, we plan to implement functions for data aggregation and estimation of population dynamics parameters.

## Requirements

- Python 3.6 or higher

## Installation

    git clone https://github.com/MoniSenNC/MoniSenForest
    cd MoniSenForest
    python3 setup.py install

Alternatively, you can install the package using pip.

    pip3 install git+https://github.com/MoniSenNC/MoniSenForest

## Usage

### Launch GUI application

    monisenforest

## Datasets of the Monitoring Sites 1000 Project

- **Tree census data** - Nation-wide tree census data from 60 forest plots (_ca._ 1 ha each) in 48 sites in Japan. The latest dataset is available [here](https://www.biodic.go.jp/moni1000/findings/data/index_file.html).

- **Litterfall data** - Nation-wide litter fall data from 21 forest plots in 20 sites in Japan. The latest dataset is available [here](https://www.biodic.go.jp/moni1000/findings/data/index_file_LitterSeed.html).

## References

1. Ishihara MI, Suzuki SN, Nakamura M _et al._ (2011) Forest stand structure, composition, and dynamics in 34 sites over Japan. _Ecological Research_, **26**, 1007–1008. [DOI: 10.1007/s11284-011-0847-y](https://doi.org/10.1007/s11284-011-0847-y)

2. Suzuki SN, Ishihara MI, Nakamura M _et al._ (2012) Nation-wide litter fall data from 21 forests of the Monitoring Sites 1000 Project in Japan. _Ecological Research_, **27**, 989–990. [DOI: 10.1007/s11284-012-0980-2](https://doi.org/10.1007/s11284-012-0980-2)

3. [Manual for plot establishment and tree measurement](http://www.biodic.go.jp/moni1000/manual/tree.pdf) - _in Japanese_

4. [Manual for sampling, sorting and measurement of litterfall](http://www.biodic.go.jp/moni1000/manual/litter_ver3.pdf) - _in Japanese_

## Licence

[MIT License](LICENSE)
