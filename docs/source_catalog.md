# 资料来源分类目录

本目录用于管理堆石混凝土资料的来源、访问权限和主题分类。

## 分类说明

- `review`：综述、发展脉络、研究现状。
- `filling_capacity`：自密实混凝土填充能力、流动与堵塞。
- `mechanical_properties`：抗压、抗拉、弹性模量、破坏形态等力学性能。
- `thermal_control`：水化热、绝热温升、温控与抗裂。
- `dam_engineering`：坝工设计、施工、工程应用和质量控制。
- `seismic_response`：抗震响应和动力分析。
- `numerical_modeling`：有限元、DEM、LBM、Peridynamics 等数值模拟。
- `institutional_access`：通过机构账号合法访问，但不公开再分发全文。

## 已下载开放全文

| source_id | 标题 | 年份 | 分类 | 访问权限 | 本地文件 |
| --- | --- | --- | --- | --- | --- |
| rfc_full_001 | Research on Rock-Filled Concrete Dam | 2017 | review; dam_engineering; construction_quality | open proceedings PDF | `data/fulltext/open_access/rfc_full_2017_jin_research_on_rfc_dam_tugraz.pdf` |
| rfc_full_002 | Lattice Boltzmann-Discrete Element Modeling Simulation of SCC Flowing Process for Rock-Filled Concrete | 2019 | filling_capacity; numerical_modeling; scc_flow | open access | `data/fulltext/open_access/rfc_full_2019_chen_lbm_dem_materials_mdpires.pdf` |
| rfc_full_003 | Experimental Research on the Properties of Rock-Filled Concrete | 2019 | mechanical_properties; field_test; material_properties | open access | `data/fulltext/open_access/rfc_full_2019_wei_properties_applsci_mdpires.pdf` |
| rfc_full_004 | Filling Capacity Evaluation of Self-Compacting Concrete in Rock-Filled Concrete | 2020 | filling_capacity; scc_flow; theoretical_model | open access | `data/fulltext/open_access/rfc_full_2020_liu_filling_capacity_materials_mdpires.pdf` |
| rfc_full_005 | A Brief Review of Rock-Filled Concrete Dams and Prospects for Next-Generation Concrete Dam Construction Technology | 2023 | review; next_generation_dams; intelligent_quality_control | open access | `data/fulltext/open_access/rfc_full_2023_jin_review_engineering.pdf` |
| rfc_full_006 | A Mesoscale Comparative Analysis of the Elastic Modulus in Rock-Filled Concrete for Structural Applications | 2024 | elastic_modulus; numerical_modeling; mechanical_properties | open access | `data/fulltext/open_access/rfc_full_2024_ihteshaam_elastic_modulus_buildings_mdpires.pdf` |
| rfc_full_007 | A Comprehensive Literature Review on the Elastic Modulus of Rock-filled Concrete | 2024 | review; elastic_modulus; mechanical_properties | open access | `data/fulltext/open_access/rfc_full_2024_ihteshaam_review_etasr.pdf` |
| rfc_full_008 | Seismic Behavior of Rock-Filled Concrete Dam Compared with Conventional Vibrating Concrete Dam Using Finite Element Method | 2024 | seismic_response; dam_engineering; numerical_modeling | open access | `data/fulltext/open_access/rfc_full_2024_tang_seismic_infrastructures_mdpires.pdf` |
| rfc_full_009 | 3D mesoscopic numerical investigation on the uniaxial compressive behavior of rock-filled concrete with different ITZ and aggregate properties | 2025 | compressive_behavior; itz; numerical_modeling | open access | `data/fulltext/open_access/rfc_full_2025_chen_3d_mesoscopic_scirep.pdf` |
| rfc_full_010 | Full-Scale micromechanical simulation of rock-filled concretes using Peridynamics | 2025 | micromechanics; peridynamics; numerical_modeling | open access | `data/fulltext/open_access/rfc_full_2025_mohajerani_peridynamics_actageotech.pdf` |

详细 URL、PDF URL、许可备注和状态见 `data/fulltext_manifest.csv`。

自动化扩容方式见 `docs/corpus_pipeline.md`。

## CNKI / 机构访问优先下载清单

这些资料可通过机构账号下载，但不应提交到 GitHub，也不应公开再分发全文。下载后建议放入：

```text
data/fulltext/cnki_pending/
```

| 优先级 | 标题 | 作者 | 年份 | 分类 | 备注 |
| --- | --- | --- | --- | --- | --- |
| P0 | 堆石混凝土及堆石混凝土大坝 / Study on rock-fill concrete dam | 金峰; 安雪晖; 石建军; 张楚汉 | 2005 | review; dam_engineering; founding_paper | 用户确认的开篇之作 |
| P0 | 自密实混凝土充填堆石体试验研究 | 安雪晖; 金峰; 石建军 | 2005 | filling_capacity; construction_quality | 早期填充能力试验 |
| P1 | 自密实堆石混凝土力学性能的试验研究 | 石建军; 张志恒; 金峰; 张楚汉 | 2007 | mechanical_properties | 早期力学性能试验 |
| P1 | 堆石混凝土绝热温升性能初步研究 | 金峰; 李乐; 周虎; 安雪晖 | 2008 | thermal_control; hydration_heat | 温控与抗裂主题 |
| P1 | Rock-filled concrete, the new norm of SCC in hydraulic engineering in China | Xuehui An; Qiong Wu; Feng Jin 等 | 2014 | review; dam_engineering | ScienceDirect 机构访问优先 |
| P1 | Experimental study of filling capacity of self-compacting concrete and its influence on the properties of rock-filled concrete | Yuetao Xie; David J. Corr; Mohend Chaouche; Feng Jin; Surendra P. Shah | 2014 | filling_capacity; material_properties | ScienceDirect 机构访问优先 |

## 已下载机构访问全文

| source_id | 标题 | 年份 | 分类 | 访问权限 | 本地文件 |
| --- | --- | --- | --- | --- | --- |
| rfc_cnki_001 | 堆石混凝土及堆石混凝土大坝 / Study on rock-fill concrete dam | 2005 | review; dam_engineering; founding_paper | CNKI institutional access | `data/fulltext/cnki_pending/rfc_cnki_2005_jin_an_study_on_rock_fill_concrete_dam.pdf` |

## 使用原则

- 开放获取 PDF 可以进入本地全文库，但回答中仍只摘取必要短句，不复制大段原文。
- 机构访问 PDF 只用于本地私有学习和检索，不提交到仓库。
- 不使用网盘盗版、破解下载、绕过验证码或反爬限制的来源。
- 每个来源都必须保留原始 URL、PDF URL、本地文件名、访问权限和主题分类。
