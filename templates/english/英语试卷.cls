% ============================================================================
%  英语试卷.cls  ——  高中英语「试题 / 参考答案」LaTeX 排版模板
% ----------------------------------------------------------------------------
%  版面参数提取自  2501浙江首考/试题.docx 与 2501浙江首考/答案.docx，
%  并用 Word 另存的 PDF 逐项量测核对：
%    纸张 A4 210×297mm；上/下页边距 25.4mm，左/右 19.05mm（1440/1080 twips）
%    正文 10.5pt（五号）：西文 Times New Roman，中文宋体，两端对齐
%    行距　：Word「单倍行距」实测 15.6pt（= 10.5 × 1.486，宋体默认行高）
%    段落首行缩进 2 字（420 twips = 21pt）；段距 0
%    卷名 16pt 粗体居中；科目名 18pt 黑体粗体居中（“英   语”拉开 1.4em）
%    「第×部分 ……」12pt 黑体粗体；「第×节（……）」10.5pt 粗体
%    页脚：华文楷体 10.5pt 居中「英语试题　第 N 页（共 M 页）」
%    写作答题区为 14pt 字、28pt 行距的空行
%  编译：xelatex（页脚总页数用 lastpage，需连编两次）
% ----------------------------------------------------------------------------
%  用法：
%    \documentclass{英语试卷}              % 试题
%    \documentclass[answers]{英语试卷}     % 参考答案（1.5 倍行距 + 页脚「英语参考答案」）
%    题型环境（choices / cloze / writinglines …）已随本类自动载入，
%    也可单独 \usepackage{英语试卷} 搭配 ctexart 使用。
% ============================================================================
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{英语试卷}[2026/11/18 v1.1 高中英语试卷/参考答案排版模板]

% OCR 偶尔产出 \pmb{\lambda} 等 LaTeX 内核缺省的命令，兜底定义防编译失败
\providecommand{\pmb}[1]{#1}

% ------------------------------ 类选项 ------------------------------
\newif\ifyy@answers   \yy@answersfalse
\DeclareOption{answers}{\yy@answerstrue}
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{ctexart}}
\ProcessOptions\relax

\LoadClass[UTF8,zihao=5,a4paper,oneside]{ctexart}

% ------------------------------ 字体 ------------------------------
\RequirePackage{fontspec}
\RequirePackage{xeCJK}
% 西文：Times New Roman（Word 正文 ascii/hAnsi 均为 Times New Roman）
\setmainfont{Times New Roman}
% 中文：宋体（正文）。SimSun 无真粗体，用 AutoFakeBold 模拟 Word 的「伪粗宋体」
\setCJKmainfont{SimSun}[AutoFakeBold=2.2,ItalicFont=KaiTi]
\setCJKsansfont{SimHei}[AutoFakeBold=2.2]
% ctex 自带的 zhkai 是「楷体」，这里改成 Word 页脚用的「华文楷体」
\setCJKfamilyfont{zhsong}{SimSun}[AutoFakeBold=2.2,ItalicFont=KaiTi]
\setCJKfamilyfont{zhhei}{SimHei}[AutoFakeBold=2.2]
\setCJKfamilyfont{zhkai}{STKaiti}
% 卷眉「绝密★启用前」用：SimHei 含 ★ 字形（宋体/黑体 CJK 字形表里没有 U+2605）
\newfontfamily{\yy@markfont}{SimHei}[BoldFont=SimHei,AutoFakeBold=2.2]

% ------------------------------ 版面 ------------------------------
\RequirePackage[a4paper,
  top=2.54cm, bottom=2.54cm,
  left=1.905cm, right=1.905cm,
  headheight=14pt, headsep=0pt, footskip=0.92cm,
  nomarginpar]{geometry}

% 首行缩进 2 字；段距 0（Word 用空行分段，这里用空行/命令控制间距）
\setlength{\parindent}{2em}
\setlength{\parskip}{0pt}
% ctex 默认 \baselinestretch=1.3，会连带放大 \fontsize{}{} 里的行距；这里归 1，
% 再用 \baselineskip 指定正文行距 = Word「单倍行距」实测的 15.6pt。
\linespread{1}
\AtBeginDocument{\linespread{1}\selectfont\setlength{\baselineskip}{15.6pt}}

% ------------------------------ 页脚 ------------------------------
\RequirePackage{fancyhdr}
\RequirePackage{lastpage}
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}
\newcommand{\yy@footerlabel}{英语试题}
\fancyfoot[C]{%
  \CJKfamily{zhkai}\fontsize{10.5pt}{12.6pt}\selectfont
  \yy@footerlabel\quad 第 \thepage\ 页（共 \pageref{LastPage} 页）}

% ------------------------------ 各级标题 ------------------------------
% 卷名 + 科目名；可选参数为左上角的「绝密★启用前」类文字
% 科目名按 Word 原样拉开：“英   语”（两字之间 1.4em）
\newcommand{\examtitle}[3][]{%
  % 先落一个空段落：TeX 会丢弃页面最顶端的胶水，直接写 \vspace 推不动卷头，
  % 有了一个空行之后，后面的 \vspace 才生效（净效果：卷头比版心顶线下沉 8.2pt）
  \noindent\mbox{}\par\vspace{-4.5pt}%
  \if\relax\detokenize{#1}\relax\else
    % Word 里「绝密★启用前」是浮在卷名左上方的文本框：
    % 用零宽盒子 + \raisebox 吊在卷名左上角，不占版面、不影响卷名居中
    \noindent\makebox[0pt][l]{\raisebox{30.6pt}[0pt][0pt]{%
      \yy@markfont\bfseries\fontsize{10.5pt}{12.6pt}\selectfont #1}}%
  \fi
  \noindent\hfil
  {\fontsize{16pt}{23.8pt}\selectfont\bfseries #2}%
  \hfil\par
  \vspace{14.6pt}%
  \noindent\hfil
  {\fontsize{18pt}{26.7pt}\selectfont\heiti\bfseries\ziju{1.4}#3}%
  \hfil\par
  \vspace{0pt}%
}

% 参考答案卷头：第二行是「科目　参考答案」，16pt，不拉开
\newcommand{\answertitle}[2]{%
  \begingroup
  \centering
  {\fontsize{16pt}{23.8pt}\selectfont\bfseries #1\par}%
  \vspace{6.4pt}%
  {\fontsize{16pt}{23.8pt}\selectfont\heiti\bfseries #2\quad 参考答案\par}%
  \endgroup
  \vspace{\yy@titleafter}%
}

% 第×部分 ……（12pt 黑体粗体）
\newcommand{\parttitle}[1]{%
  \par\vspace{\yy@partbefore}%
  {\setlength{\parindent}{0pt}%
   \fontsize{12pt}{17.8pt}\selectfont\heiti\bfseries #1\par}%
  \vspace{\yy@partafter}%
}

% 第×节（……）（10.5pt 粗体）
\newcommand{\sectitle}[1]{%
  \par\vspace{\yy@secbefore}%
  {\setlength{\parindent}{0pt}\bfseries #1\par}%
  \vspace{\yy@secafter}%
}

% 注意事项
\newenvironment{notice}{%
  \par\vspace{5.3pt}%
  {\setlength{\parindent}{0pt}\heiti 注意事项：}\par
  \vspace{0pt}%
  \begingroup
  \setlength{\parindent}{2em}%
}{%
  \endgroup\par\vspace{0pt}%
}

% 题干（顶格，不缩进；Word 中题干与选项之间只隔一个行距）
\newcommand{\question}[1]{\par\noindent #1\par}

% 作文标题（居中粗体）
\newcommand{\writingtitle}[1]{%
  \par\vspace{0.4em}%
  \begingroup\centering\bfseries #1\par\endgroup
  \vspace{0.3em}%
}

% 阅读文章编号 A / B / C / D（居中粗体）
\newcommand{\passagelabel}[1]{%
  \par\vspace{0.7em}%
  \begingroup\centering\bfseries #1\par\endgroup
  \vspace{0.3em}%
}

% 语法填空/短文改错空位：题号居中压在下划线上；\blanknum{} 表示无题号的空线
\newcommand{\blanknum}[1]{\underline{\makebox[2.4em]{\hfil#1\hfil}}}

% ------------------------------ 题型环境 ------------------------------
\RequirePackage{英语试卷}

% 参考答案模式：1.5 倍行距（实测 23.7pt）+ 页脚「英语参考答案」。
% 答案文档行距大，各级标题与答案行的前后间距按 答案.docx 重新量测，
% 因此出现负值（标题行高占满了行距，需往回找补），属正常。
\ifyy@answers
  \AtBeginDocument{\linespread{1}\selectfont\setlength{\baselineskip}{23.7pt}}
  \renewcommand{\yy@footerlabel}{英语参考答案}
  \renewcommand{\yy@partbefore}{5.8pt}%
  \renewcommand{\yy@partafter}{-0.5pt}%
  \renewcommand{\yy@secbefore}{-2.1pt}%
  \renewcommand{\yy@secafter}{3.7pt}%
  \renewcommand{\yy@ansbefore}{0pt}%
  \renewcommand{\yy@ansafter}{0pt}%
  \renewcommand{\yy@titleafter}{6pt}%
\fi

\endinput
