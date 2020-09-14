MoniSenForest
-------------

MoniSenForest is a tool for handling the tree census data and litterfall data of the Monitoring Sites 1000 Project (also called "Moni-Sen") in Japan.

* **Tree census data** - Nation-wide tree census data from 60 forest plots (*ca.* 1 ha each) in 48 sites in Japan. The latest dataset is available [here](https://www.biodic.go.jp/moni1000/findings/data/index_file.html). 

* **Litterfall data** - Nation-wide litter fall data from 21 forest plots in 20 sites in Japan. The latest dataset is available [here](https://www.biodic.go.jp/moni1000/findings/data/index_file_LitterSeed.html). 


## Features

The aim of MoniSenForest is to support data error checking for data collecters and to provide easy-to-use data pre-processing methods for people who work with data.

Currently, MoniSenForest implements functions such as data cleaning and translation of species names from Japanese names to scientific names. In future updates, we plan to implement functions for data aggregation and estimation of population dynamics parameters.


## Requirements

* Python 3.6 or higher


## Installation

    git clone https://github.com/kohyamat/MoniSenForest
    cd MoniSenForest
    python3 setup.py install

Alternatively, you can install the package using pip.

    pip3 install git+https://github.com/kohyamat/MoniSenForest


## Launch GUI application

    monisenforest


## References

1. Ishihara MI, Suzuki SN, Nakamura M *et al.* (2011) Forest stand structure, composition, and dynamics in 34 sites over Japan. *Ecological Research*, **26**, 1007–1008. [DOI: 10.1007/s11284-011-0847-y](https://doi.org/10.1007/s11284-011-0847-y)

2. Suzuki SN, Ishihara MI, Nakamura M *et al.* (2012) Nation-wide litter fall data from 21 forests of the Monitoring Sites 1000 Project in Japan. *Ecological Research*, **27**, 989–990. [DOI: 10.1007/s11284-012-0980-2](https://doi.org/10.1007/s11284-012-0980-2)

3. [モニタリングサイト1000 森林・草原調査 コアサイト設定・毎木調査マニュアル](http://www.biodic.go.jp/moni1000/manual/tree.pdf) (Manual for plot establishment and measurement - *in Japanese*)

4. [モニタリングサイト1000 森林・草原調査 落葉落枝・落下種子調査マニュアル](http://www.biodic.go.jp/moni1000/manual/litter_ver3.pdf) (Manual for sampling, sorting and measurement of litterfall - *in Japanese*)

## Licence

[MIT License](LICENSE)
