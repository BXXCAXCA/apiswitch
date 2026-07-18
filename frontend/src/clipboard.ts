export async function copyText(value: string): Promise<void> {
  if (!value) throw new Error('没有可复制的内容')
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
      return
    }
  } catch {
    // Desktop WebView permission policies can reject the modern API. Use the
    // synchronous selection fallback below while the button click is active.
  }

  const textarea = document.createElement('textarea')
  textarea.value = value
  textarea.readOnly = true
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  textarea.style.pointerEvents = 'none'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  textarea.setSelectionRange(0, value.length)
  const copied = typeof document.execCommand === 'function' && document.execCommand('copy')
  textarea.remove()
  if (!copied) throw new Error('系统拒绝访问剪贴板，请选中 Token 后按 Ctrl+C')
}
