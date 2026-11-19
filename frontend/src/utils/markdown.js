
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'
import { katex } from '@mdit/plugin-katex'

// 代码高亮样式
import 'highlight.js/styles/github-dark.css'

// 数学公式样式
import 'katex/dist/katex.min.css'

// 创建 Markdown 渲染器
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,

  highlight(code, language) {
    const requestedLanguage = (language || '')
      .trim()
      .split(/\s+/)[0]
      .toLowerCase()

    const aliases = {
      'c++': 'cpp',
      'c#': 'csharp',
      js: 'javascript',
      ts: 'typescript',
      py: 'python',
      sh: 'bash',
      shell: 'bash'
    }

    const lang =
      aliases[requestedLanguage] || requestedLanguage

    let highlightedCode

    if (lang && hljs.getLanguage(lang)) {
      try {
        highlightedCode = hljs.highlight(code, {
          language: lang,
          ignoreIllegals: true
        }).value
      } catch (error) {
        console.error('代码高亮失败：', error)
        highlightedCode = md.utils.escapeHtml(code)
      }
    } else {
      highlightedCode = md.utils.escapeHtml(code)
    }

    const languageLabel = md.utils
      .escapeHtml(requestedLanguage || 'text')
      .toUpperCase()

    return `
      <div class="code-block-wrapper">
        <div class="code-block-toolbar">
          <span class="code-language">
            ${languageLabel}
          </span>
          <button
            type="button"
            class="code-copy-button"
          >
            复制
          </button>
        </div>
        <pre class="hljs"><code>${highlightedCode}</code></pre>
      </div>
    `
  }
})

// 启用 LaTeX 数学公式渲染
md.use(katex, {
  delimiters: 'all',
  throwOnError: false
})

// Markdown 转换 + HTML 安全过滤
export function renderMarkdown(content) {
  const html = md.render(String(content ?? ''))

  return DOMPurify.sanitize(html, {
    USE_PROFILES: {
      html: true,
      mathMl: true
    },
    ADD_TAGS: ['button'],
    ADD_ATTR: ['type']
  })
}
