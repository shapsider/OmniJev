---
task_categories:
- multiple-choice
- question-answering
- visual-question-answering
language:
- en
size_categories:
- 1K<n<10K
configs:
- config_name: val
  data_files:
  - split: val
    path: "mmstar.parquet"
dataset_info:
  - config_name: val
    features:
      - name: index
        dtype: int64
      - name: question
        dtype: string
      - name: image
        dtype: image
      - name: answer
        dtype: string
      - name: category
        dtype: string
      - name: l2_category
        dtype: string
      - name: meta_info
        struct:
        - name: source
          dtype: string
        - name: split
          dtype: string
        - name: image_path
          dtype: string
    splits:
      - name: val
        num_bytes: 44831593
        num_examples: 1500
---

# MMStar (Are We on the Right Way for Evaluating Large Vision-Language Models?)

[**🌐 Homepage**](https://mmstar-benchmark.github.io/) | [**🤗 Dataset**](https://huggingface.co/datasets/Lin-Chen/MMStar) | [**🤗 Paper**](https://huggingface.co/papers/2403.20330) | [**📖 arXiv**](https://arxiv.org/pdf/2403.20330.pdf) | [**GitHub**](https://github.com/MMStar-Benchmark/MMStar)

## Dataset Details

As shown in the figure below, existing benchmarks lack consideration of the vision dependency of evaluation samples and potential data leakage from LLMs' and LVLMs' training data.

<p align="center">
    <img src="https://raw.githubusercontent.com/MMStar-Benchmark/MMStar/main/resources/4_case_in_1.png" width="80%"> <br>
</p>

Therefore, we introduce MMStar: an elite vision-indispensible multi-modal benchmark, aiming to ensure each curated sample exhibits **visual dependency**, **minimal data leakage**, and **requires advanced multi-modal capabilities**.

🎯 **We have released a full set comprising 1500 offline-evaluating samples.** After applying the coarse filter process and manual review, we narrow down from a total of 22,401 samples to 11,607 candidate samples and finally select 1,500 high-quality samples to construct our MMStar benchmark.

<p align="center">
    <img src="https://raw.githubusercontent.com/MMStar-Benchmark/MMStar/main/resources/data_source.png" width="80%"> <br>
</p>

In MMStar, we display **6 core capabilities** in the inner ring, with **18 detailed axes** presented in the outer ring. The middle ring showcases the number of samples for each detailed dimension. Each core capability contains a meticulously **balanced 250 samples**. We further ensure a relatively even distribution across the 18 detailed axes.

<p align="center">
    <img src="https://raw.githubusercontent.com/MMStar-Benchmark/MMStar/main/resources/mmstar.png" width="60%"> <br>
</p>

## 🏆 Mini-Leaderboard
We show a mini-leaderboard here and please find more information in our paper or [homepage](https://mmstar-benchmark.github.io/).

| Model                      | Acc. | MG ⬆ | ML ⬇ |
|----------------------------|:---------:|:------------:|:------------:|
| GPT4V (high)| **57.1**  |      **43.6**       | 1.3 |
| InternLM-Xcomposer2|  55.4 |      28.1       | 7.5|
| LLaVA-Next-34B |52.1|29.4|2.4|
|GPT4V (low)|46.1|32.6|1.3|
|InternVL-Chat-v1.2|43.7|32.6|**0.0**|
|GeminiPro-Vision|42.6|27.4|**0.0**|
|Sphinx-X-MoE|38.9|14.8|1.0|
|Monkey-Chat|38.3|13.5|17.6|
|Yi-VL-6B|37.9|15.6|**0.0**|
|Qwen-VL-Chat|37.5|23.9|**0.0**|
|Deepseek-VL-7B|37.1|15.7|**0.0**|
|CogVLM-Chat|36.5|14.9|**0.0**|
|Yi-VL-34B|36.1|18.8|**0.0**|
|TinyLLaVA|36.0|16.4|7.6|
|ShareGPT4V-7B|33.0|11.9|**0.0**|
|LLaVA-1.5-13B|32.8|13.9|**0.0**|
|LLaVA-1.5-7B|30.3|10.7|**0.0**|
|Random Choice|24.6|-|-|

## 📧 Contact

- [Lin Chen](https://lin-chen.site/): chlin@mail.ustc.edu.cn
- [Jinsong Li](https://li-jinsong.github.io/): lijingsong@pjlab.org.cn

## ✒️ Citation

If you find our work helpful for your research, please consider giving a star ⭐ and citation 📝
```bibtex
@article{chen2024we,
  title={Are We on the Right Way for Evaluating Large Vision-Language Models?},
  author={Chen, Lin and Li, Jinsong and Dong, Xiaoyi and Zhang, Pan and Zang, Yuhang and Chen, Zehui and Duan, Haodong and Wang, Jiaqi and Qiao, Yu and Lin, Dahua and others},
  journal={arXiv preprint arXiv:2403.20330},
  year={2024}
}
```