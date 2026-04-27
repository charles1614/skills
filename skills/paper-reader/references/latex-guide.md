# LaTeX Generation Guide for Paper Reader Skill

This guide contains critical instructions for converting the Markdown analysis into a compilable XeLaTeX document using the template at `assets/template.tex`.

## Template Usage

### Placeholders to Replace

In the template, replace these placeholders with actual content:

| Placeholder | Replace with |
|-------------|-------------|
| `%PAPER_TITLE%` | Paper title (can contain CJK characters) |
| `%PAPER_AUTHORS%` | Author names |
| `%PAPER_VENUE%` | Conference/journal name |
| `%PAPER_YEAR%` | Publication year |
| `%ONE_LINE_SUMMARY%` | One-line significance statement in Chinese |

### Filling Content Sections

Uncomment the section templates and fill in the analysis content between `\section{...}` commands. Each section from the analysis prompt maps to a LaTeX section.

## xeCJK Critical Rules

### DO:

- Use `\text{中文}` for Chinese text inside math environments
- Place `~` (non-breaking space) between Chinese text and inline math: `其中~$x$ 表示输入`
- Use `\sffamily` for Chinese headings (matches Noto Sans CJK SC)
- Escape special LaTeX characters in text: `\%`, `\&`, `\#`, `\_`, `\$`
- Use `\textbf{}` for bold Chinese text
- Use `--` for en-dash, `---` for em-dash
- Reference Latin fonts by filename (TeX Gyre fonts are in the TeX tree, not fontconfig):
  ```latex
  \setmainfont{texgyretermes}[Extension=.otf, UprightFont=*-regular, BoldFont=*-bold, ItalicFont=*-italic, BoldItalicFont=*-bolditalic]
  ```

### DON'T:

- Never put raw CJK characters inside `\label{}`, `\ref{}`, `\cite{}` — use ASCII-only identifiers
- Never use `\mbox{}` for Chinese text in math mode — use `\text{}` from amsmath
- Never use `\verb` or `verbatim` with CJK — use `listings` instead
- Never place CJK characters in `\url{}`
- Avoid stray CJK characters in comments of algorithm environments
- Never use `\textbf{Title：}~Body text...` for standalone bold headings followed by a paragraph — this renders inline (run-on) with no visual separation. Use `\paragraph{Title}` instead, which produces a bold heading with proper spacing:

  ```latex
  % BAD — runs together as one paragraph:
  \textbf{挑战一：MLA 的训练问题。}~MLA 使用 Muon 时性能不及 GQA...

  % GOOD — title on its own line with spacing:
  \paragraph{挑战一：MLA 的训练问题}
  MLA 使用 Muon 时性能不及 GQA...
  ```

  **When to use which**: If Markdown has `**Bold title：** body text` as a standalone labeled paragraph (e.g., challenges, subsystem descriptions), convert to `\paragraph{}`. If it's inline emphasis within a sentence, keep `\textbf{}`. The template redefines `\paragraph` to keep proper post-spacing even when followed directly by an environment, so `\paragraph{Title.}\begin{keyinsight}...\end{keyinsight}` is safe.

- For long URLs, GitHub paths, namespaced identifiers, or any monospace tokens that contain `/`, `@`, `_`, `-`, or `.`, prefer `\path{...}` over `\texttt{...}`. The template configures `\path` (via the `url` package) to break naturally at those characters, preventing CJK-justified lines from stretching when a long path appears inline.

- For 2-column key/value tables inside `infobox` (e.g. paper-info, evaluation matrices, configuration summaries), use `\begin{infotable} ... \end{infotable}` instead of `\begin{tabular}{p{Ncm}p{Mcm}}`. `infotable` is a template-provided environment that auto-sizes via `tabularx{\linewidth}{p{2.8cm}X}` to fit the box's interior — fixed-cm column specs frequently overflow because `infobox` has internal padding.

  ```latex
  % BAD — fixed columns can exceed the box's interior width:
  \begin{infobox}[论文信息]
  \begin{tabular}{@{}p{3.2cm}p{13cm}@{}}    % 16.2cm > ~15.4cm interior
  \textbf{标题} & ... \\
  \end{tabular}
  \end{infobox}

  % GOOD — auto-sizing fits the box exactly:
  \begin{infobox}[论文信息]
  \begin{infotable}
  \textbf{标题} & ... \\
  \end{infotable}
  \end{infobox}
  ```

  For 3+ column tables, use `tabularx{\linewidth}{l l X}` directly (one `X` column to absorb remaining width).

  ```latex
  % BAD — long token can't break, forces preceding Chinese text to stretch:
  通过 HuggingFace \texttt{deepseek-ai/DeepSeek-V4-Flash} 仓库发布

  % GOOD — \path{} breaks at /, -, etc.:
  通过 HuggingFace \path{deepseek-ai/DeepSeek-V4-Flash} 仓库发布
  ```

## Code Examples

### Equation with Chinese explanation

```latex
\begin{mathbox}[目标函数]
本文的核心优化目标为：
\begin{equation}
  \mathcal{L}(\theta) = \sum_{i=1}^{N} \ell\bigl(f_\theta(x_i),\, y_i\bigr) + \lambda \|\theta\|_2^2
  \label{eq:objective}
\end{equation}
其中~$f_\theta$ 表示参数化模型，$\ell(\cdot,\cdot)$ 为任务相关损失函数，$\lambda$ 控制正则化强度。
\end{mathbox}
```

### Algorithm pseudocode

```latex
\begin{algorithm}[htbp]
\caption{核心算法名称}
\label{alg:core}
\begin{algorithmic}[1]
\REQUIRE 输入数据~$\mathcal{D} = \{(x_i, y_i)\}_{i=1}^N$，学习率~$\eta$
\ENSURE 最优参数~$\theta^*$
\STATE 初始化参数~$\theta_0$
\FOR{$t = 1$ \TO $T$}
  \STATE 采样 mini-batch $\mathcal{B} \subset \mathcal{D}$
  \STATE 计算梯度~$g_t \leftarrow \nabla_\theta \mathcal{L}(\theta_{t-1}; \mathcal{B})$
  \STATE 更新参数~$\theta_t \leftarrow \theta_{t-1} - \eta \cdot g_t$
\ENDFOR
\RETURN $\theta_T$
\end{algorithmic}
\end{algorithm}
```

### Comparison table with booktabs

```latex
\begin{table}[htbp]
\centering
\caption{方法性能对比}
\label{tab:comparison}
\begin{tabular}{lccc}
\toprule
\textbf{方法} & \textbf{准确率 (\%)} & \textbf{推理速度} & \textbf{参数量} \\
\midrule
Baseline A       & 85.2 & 1.0$\times$ & 110M \\
Baseline B       & 87.4 & 0.8$\times$ & 340M \\
\textbf{本文方法} & \textbf{91.7} & \textbf{1.3$\times$} & 125M \\
\bottomrule
\end{tabular}
\end{table}
```

### Strengths box

```latex
\begin{strengthbox}
\begin{itemize}
  \item \gmark{创新性}：提出了全新的注意力机制，突破了传统方法的二次复杂度瓶颈
  \item \gmark{实验充分}：在5个标准数据集上进行了全面评估，包含完整的消融实验
  \item \gmark{工程价值}：提供了开源实现，代码组织清晰，易于复现
\end{itemize}
\end{strengthbox}
```

### Weaknesses box

```latex
\begin{weaknessbox}
\begin{itemize}
  \item \rmark{泛化性}：实验仅覆盖英文数据集，对多语言场景的适用性未经验证
  \item \rmark{计算开销}：尽管理论复杂度降低，但实际 wall-clock 时间仅缩短15\%
  \item \rmark{假设过强}：要求输入数据满足独立同分布假设，限制了实际应用范围
\end{itemize}
\end{weaknessbox}
```

### Key insight box

```latex
\begin{keyinsight}[本节核心要点]
本文的核心创新在于将稀疏注意力机制与混合专家架构相结合，在保持模型容量的同时将推理计算量降低至原来的~$1/k$。
\end{keyinsight}
```

### Info box for metadata

```latex
\begin{infobox}[论文信息]
\begin{tabular}{@{}p{2.5cm}p{10cm}@{}}
\textbf{标题} & Attention Is All You Need \\
\textbf{作者} & Vaswani, Shazeer, Parmar et al. (Google Brain) \\
\textbf{发表} & NeurIPS 2017 \\
\textbf{类型} & ML/DL 算法论文 \\
\textbf{核心领域} & NLP, Sequence Modeling \\
\end{tabular}
\end{infobox}
```

### Long equations (avoiding overflow)

Equations in academic papers often contain repeated subexpressions (e.g., policy ratios, attention scores) that make a single-line `equation` overflow. **Always check if an equation will fit in one line** — if it has more than ~80 characters of math content or repeated fractions, it will likely overflow.

**Strategy 1: Introduce shorthand notation** (preferred when a subexpression repeats 2+ times):

```latex
\begin{mathbox}[策略优化目标]
令~$\rho_j^i = \frac{\pi_\theta(y_j^i \mid x,\, y_j^{0:i})}{\pi_{\text{old}}(y_j^i \mid x,\, y_j^{0:i})}$，则：
\begin{equation}
  L(\theta) = \mathbb{E}_{x \sim D}\!\Biggl[\,
    \frac{1}{N}\sum_{j=1}^{K}\sum_{i=1}^{|y_j|}
    \text{Clip}\bigl(\rho_j^i,\;\alpha,\;\beta\bigr)
    \bigl(r(x,y_j) - \bar{r}(x)\bigr)
    - \tau\bigl(\log \rho_j^i\bigr)^2
  \,\Biggr]
  \label{eq:objective}
\end{equation}
\end{mathbox}
```

**Strategy 2: Multi-line with `split`** (when the equation has distinct additive/subtractive terms):

```latex
\begin{equation}
\begin{split}
  \mathcal{L}(\theta) &= \sum_{i=1}^{N} \ell\bigl(f_\theta(x_i),\, y_i\bigr)
    + \lambda_1 \|\theta\|_2^2 \\
  &\quad + \lambda_2 \sum_{j \in \mathcal{N}(i)} d\bigl(f_\theta(x_i),\, f_\theta(x_j)\bigr)
\end{split}
\label{eq:loss}
\end{equation}
```

**Strategy 3: `multline`** (when there's no natural alignment point):

```latex
\begin{multline}
  p(x_1, x_2, \ldots, x_n) = p(x_1) \cdot p(x_2 \mid x_1)
    \cdot p(x_3 \mid x_1, x_2) \\
    \cdots p(x_n \mid x_1, \ldots, x_{n-1})
\label{eq:chain}
\end{multline}
```

**Rule of thumb**: If a formula from the paper has deeply nested fractions or long subscripts/superscripts repeated multiple times, define a shorthand variable first (`令~$\rho = ...$`), then write the main equation using the shorthand. This is both more readable and avoids overflow.

### Qualitative assessment table

```latex
\begin{table}[htbp]
\centering
\caption{定性评估}
\begin{tabular}{llp{0.55\textwidth}}
\toprule
\textbf{评估维度} & \textbf{评级} & \textbf{说明} \\
\midrule
新颖性     & 显著创新    & 完全抛弃循环结构，开创性提出纯注意力架构 \\
技术严谨性 & 高         & 数学表述清晰，实验设计合理 \\
实验充分性 & 充分       & 多个翻译基准 + 消融实验 \\
可复现性   & 高         & 代码开源，超参数详细 \\
写作质量   & 优秀       & 结构清晰，图表直观 \\
\bottomrule
\end{tabular}
\end{table}
```

### Single figure with Chinese caption

```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=0.85\textwidth]{figures/fig1_architecture.png}
\caption{系统整体架构图。本文提出的框架由三个核心模块组成：编码器、注意力层和解码器。}
\label{fig:architecture}
\end{figure}
```

### Side-by-side figures

```latex
\begin{figure}[htbp]
\centering
\begin{subfigure}[b]{0.48\textwidth}
  \includegraphics[width=\textwidth]{figures/fig2a_result.png}
  \caption{在数据集A上的性能对比}
  \label{fig:result-a}
\end{subfigure}
\hfill
\begin{subfigure}[b]{0.48\textwidth}
  \includegraphics[width=\textwidth]{figures/fig2b_result.png}
  \caption{在数据集B上的性能对比}
  \label{fig:result-b}
\end{subfigure}
\caption{核心实验结果。本文方法（红色）在两个数据集上均显著优于基线。}
\label{fig:results}
\end{figure}
```

### Full-width figure spanning the page

```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=\textwidth]{figures/fig3_pipeline.png}
\caption{端到端训练流程。数据经过预处理、特征提取、模型推理和后处理四个阶段。}
\label{fig:pipeline}
\end{figure}
```

### Figure cross-reference in text

```latex
如图~\ref{fig:architecture} 所示，系统整体采用 Encoder-Decoder 架构。
实验结果（图~\ref{fig:results}）表明，本文方法在准确率上提升了5.2\%。
```

### Rating display

```latex
新颖性：\ratingfull\ratingfull\ratingfull\ratingfull\ratinghalf
```

## Compilation Instructions

```bash
# First pass (generates .aux for TOC and cross-refs)
xelatex -interaction=nonstopmode paper_analysis.tex

# Second pass (resolves cross-references and TOC)
xelatex -interaction=nonstopmode paper_analysis.tex
```

### Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `Missing $ inserted` | CJK character leaked into math mode | Wrap Chinese text in `\text{}` |
| `Undefined control sequence \CJK...` | xeCJK not loaded | Ensure `\usepackage{xeCJK}` is present |
| `Font ... not found` | Missing system font | For CJK: check `fc-list :lang=zh`; For Latin: use filename-based font loading (see template) |
| `Missing \begin{document}` | Encoding issue | Ensure file is saved as UTF-8 without BOM |
| `Overfull \hbox` | Long formula or URL | For equations: use shorthand notation, `split`, or `multline` (see "Long equations" section above). For URLs: use `\url{}` with hyperref. For tables: use `p{width}` columns instead of `l` for long text. |
| `Package tcolorbox Error` | Missing tcolorbox library | Use `\usepackage[most]{tcolorbox}` |

### Figure-related Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `File 'figures/fig1.png' not found` | Image file missing or wrong path | Verify `figures/` directory exists alongside `.tex` file; check filename spelling |
| `Dimension too large` | Image resolution extremely high | Add `\includegraphics[width=\textwidth,height=0.4\textheight,keepaspectratio]{...}` to constrain |
| `Unknown graphics extension` | File not PNG/JPG/PDF | Convert to PNG: `convert input.ppm output.png` |

### Post-compilation Check

After successful compilation, verify:
1. Chinese text renders correctly (not boxes or question marks)
2. Table of contents shows all sections with correct page numbers
3. Mathematical formulas display properly
4. Colored boxes render with correct backgrounds and borders
5. Hyperlinks in TOC and cross-references are clickable
6. **Figures display correctly** — not cropped, properly sized, captions visible
