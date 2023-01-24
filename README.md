# NIMF (Negative Interaction by Maximum Flow)

### Generation of negative enhancer-promoter interactions 

The main script is extended_region_research/main.py.

### Libraries 
---

| Library | Version |
| :---: | :---: |
| ```pandas``` | TD |
| ```numpy``` | TD |
| ```biopython``` | TD |
| ```gensim``` | TD |
| ```pybedtools``` | TD |
| ```sklearn``` | TD |
| `````` | TD |
| `````` | TD |
| `````` | TD |
| `````` | TD |
| `````` | TD |


### Directory structure
---

```
data_root_path (引数でパスを指定してください．子のフォルダが自動で生成されます．)  
├── bed  
│   ├── enhancer  
│   └── promoter  
├── fasta  
│   ├── enhancer  
│   └── promoter  
├── reference_genome  
├── d2v  
├── train  
├── result  
└── log  



extended_reginon_research  
├── main.py  
├── make_directory.py  
├── data_download.py  
├── data_processing.py  
├── my_doc2vec.py  
├── train_classifier.py  
├── t_sne.py  
├── make_args_logfile.py  
└── utils.py  
```

### Argument (課題：説明雑な部分を直す)
---

| argument | default value | description |
| :---: | :---: | ---- |
| ```-my_data_folder_path``` | 無し | 必要なデータがこのフォルダーをルートパスとして生成されます．必ず指定してください |
| ```--make_directory``` | 無し | 必要なディレクトリを```-my_data_folder_path```中に生成します |
| ```--download_reference_genome``` | 無し | hg19のリファレンスゲノムをgenome browserからダウンロードします． |
| ```--cell_line_list``` | ```K562``` | 実験に用いる細胞株 |
| ```--E_extended_left_length``` | ```10``` | エンハンサーの上流の延長する長さ |
| ```--E_extended_right_length``` | ```20``` | エンハンサーの上流の延長する長さ |
| ```--P_extended_left_length``` | ```30``` | エンハンサーの上流の延長する長さ |
| ```--P_extended_right_length``` | ```40``` | エンハンサーの上流の延長する長さ |
| ```--embedding_vector_dimention``` | TD | doc2vecによるparagraph vectorの次元数 |
| ```--way_of_kmer``` | ```normal``` | k-merの切り方(```normal``` or ```random```)|
| ```--k``` | ```6``` | ```--way_of_kmer == normal``` の時のk |
| ```--stride``` | ```1``` | ```--way_of_kmer == normal``` の時のstride |
| ```--sentence_cnt``` | ? | TD |
| ```--k_min``` | ```3``` | ```--way_of_kmer == random``` の時のk_min |
| ```--k_max``` | ```6``` | ```--way_of_kmer == random``` の時のk_max |

### Example
---
```main.py -my_data_folder_path /Users/ylwrvr/卒論/Koga_code/data --cell_line_list GM12878 --make_directory --download_reference_genome --share_doc2vec ```
