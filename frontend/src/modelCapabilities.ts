export type CapabilityOption = { label: string; value: string }

export const inputCapabilityOptions: CapabilityOption[] = [
  { label: '文本 text', value: 'text' },
  { label: '视觉 vision', value: 'vision' },
  { label: '文件 files', value: 'files' },
  { label: '音频 audio', value: 'audio' },
  { label: '视频 video', value: 'video' },
  { label: '工具结果 tool_results', value: 'tool_results' },
  { label: '长上下文 long_context', value: 'long_context' }
]

export const outputCapabilityOptions: CapabilityOption[] = [
  { label: '文本 text', value: 'text' },
  { label: '工具 tools', value: 'tools' },
  { label: '结构化 JSON', value: 'json' },
  { label: '向量 embeddings', value: 'embeddings' },
  { label: '图像 images', value: 'images' },
  { label: '音频 audio', value: 'audio' },
  { label: '视频 video', value: 'video' },
  { label: '音乐 music', value: 'music' },
  { label: '内容审核 moderation', value: 'moderation' },
  { label: '重排 rerank', value: 'rerank' },
  { label: '搜索 search', value: 'search' }
]

export const allCapabilityOptions: CapabilityOption[] = Array.from(
  new Map([...inputCapabilityOptions, ...outputCapabilityOptions].map(option => [option.value, option])).values()
)
