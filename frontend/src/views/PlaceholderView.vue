<template>
  <n-card>
    <n-h1>{{ title }}</n-h1>
    <n-empty description="第一阶段已预留页面结构，后续阶段接入真实功能。" />
  </n-card>
</template>

<script setup lang="ts">
import { NCard, NEmpty, NH1 } from 'naive-ui'
defineProps<{ title: string }>()
</script>
