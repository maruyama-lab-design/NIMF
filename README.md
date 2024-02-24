# CBMF (Class Balanced negative set by Maximum-Flow) and CBGS (Class Balanced negative set by Gibbs Sampling)

This repository contains files related to our methods, CBMF and CBGS, which generate a set of negative enhancer-promoter interactions (EPIs) given a set of positive EPIs. 

Details of the directory structure of this repository are as follows.

```
CBOEP (Repository)
├── cbmf.py
├── cbgs.py
├── input_to_neg_generator
├── output_from_neg_generator
└── EPI_predictor
```
`cbmf.py` and `cbgs.py` is the main execution file of CBMF and CBGS, respectively.



# Datasets
CBMF and CBGS require a positive EPIs set as input to generate the new dataset.

We already have EPIs sets for BENGI and TargetFinder in ```input_to_neg_generator```.

If you want to generate the negative EPIs set from your EPIs set,
please note that your EPIs set should be csv format with the following columns:

| Column | Description |
| :---: | --- |
| ```label``` | ```1``` for positive EPI, ```0``` for negative EPI |
| ```enhancer_distance_to_promoter``` | Distance between the enhancer and the promoter |
| ```enhancer_chrom``` | Chromosome number of the enhancer |
| ```enhancer_start``` | Start position of the enhancer |
| ```enhancer_end``` | End position of the enhancer |
| ```enhancer_name``` | Name of the enhancer, such as `GM12878\|chr16:88874-88924` |
| ```promoter_chrom``` | Chromosome number of the promoter |
| ```promoter_start``` | Start position of the promoter |
| ```promoter_end``` | End position of the promoter |
| ```promoter_name``` | Name of the promoter, such as `GM12878\|chr16:103009-103010`|

# How to generate the new CBMF dataset
`cbmf.py` is the executable file to generate CBMF-negative EP pairs. 


## Requirements
We have tested the work in the following environments.

| Library | Version |
| :---: | :---: |
|```python```|3.12.1|
| ```numpy``` |1.26.3|
| ```pandas``` |2.2.0|
| ```pulp``` | 2.8.0 |


## Argument
---

| Argument | Default value | Description |
| :---: | :---: | ---- |
| ```-input``` ||Path to the input EPI dataset.|
| ```-output``` ||Path to the output EPI dataset|
| ```-dmax``` |2,500,000|Upper bound of enhancer-promoter distance for newly generated negative EPIs.|
| ```-dmin``` |0|Lower bound of enhancer-promoter distance for newly generated negative EPIs.|
| ```--concat``` |False|Whether or not to concatenate the CBMF negative set with the positive set given as input. If not given, only the CBMF negative set will be output.|



## Execution example
```  
python cbmf.py \
-infile ./input_to_neg_generator/normalized_BENGI/GM12878.csv \
-outfile ./output_from_neg_generator/normalized_BENGI/GM12878.csv \
-dmax 2500000 \
-dmin 0 \
--concat
```




# How to generate the new CBGS dataset

`cbgs.py` is the executable file to generate CBGS-negative EP pairs. 

## Requirements

We have tested the work in the following environments.

| Library | Version |
| :---: | :---: |
|```python```|3.12.1|
| ```numpy``` |1.26.3|
| ```pandas``` |2.2.0|
| ```matplotlib``` | 3.8.2 |

## Argument
---

| Argument | Default value | Description |
| :---: | :---: | ---- |
| ```-input``` ||Path to the input EPI dataset.|
| ```-output``` ||Path to the output EPI dataset|
| ```-dmax``` |2,500,000|Upper bound of enhancer-promoter distance for newly generated negative EPIs.|
| ```-dmin``` |0|Lower bound of enhancer-promoter distance for newly generated negative EPIs.|
|```--T```|40,000|Number of sampling iteration|
| ```--concat``` ||If given, the CBGS negative set is concatenated with the positive set given as input. If not given, only the CBGS negative set will be output.|
|```--make_fig```||If given, a figure which shows plots of the mean of positive/negative class imbalance of all enhancers and promoters for each sampling iteration is made.|
|```--out_figfile```||If ```--make_fig``` is given, a figure is saved in this path.|


## Execution example
```  
python cbgs.py \
-infile ./input_to_neg_generator/normalized_BENGI/GM12878.csv \
-outfile ./output_from_neg_generator/BENGI-P_CBGS-N/dmax_2500000/GM12878.csv \
-dmax 2500000 \
-dmin 0 \
--concat \
--make_fig \
--out_figfile ./output_from_neg_generator/BENGI-P_CBGS-N/dmax_2500000/GM12878.png
```







