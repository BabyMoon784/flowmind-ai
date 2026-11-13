
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'

// 代码高亮主题
import 'highlight.js/styles/github-dark.css'

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

    // 处理常见语言别名
    const aliases = {
      'c++': 'cpp',
      'c#': 'csharp',
      'js': 'javascript',
      'ts': 'typescript',
      'py': 'python',
      'sh': 'bash',
      'shell': 'bash'
    }

    const lang = aliases[requestedLanguage] || requestedLanguage

    let highlightedCode

    // 有对应语言时进行语法高亮
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
      // 未指定语言或不支持的语言，安全显示普通代码
      highlightedCode = md.utils.escapeHtml(code)
    }

    // 安全处理语言名称
    const languageLabel = md.utils.escapeHtml(
      requestedLanguage || 'text'
    ).toUpperCase()

    // 生成带复制按钮的代码块
    return `
      <div class="code-block-wrapper">
        <div class="code-block-toolbar">
          <span class="code-language">${languageLabel}</span>

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

// Markdown 转换与 HTML 安全过滤
export function renderMarkdown(content) {
  const html = md.render(String(content ?? ''))

  return DOMPurify.sanitize(html, {
    USE_PROFILES: {
      html: true
    },
    ADD_TAGS: ['button'],
    ADD_ATTR: ['type']
  })
}
