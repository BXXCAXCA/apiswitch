<template>
  <n-checkbox-group :value="modelValue" class="capability-checkbox-group" @update:value="update">
    <n-space wrap>
      <n-checkbox v-for="option in options" :key="option.value" :value="option.value" :label="option.label" />
    </n-space>
  </n-checkbox-group>
</template>

<script setup lang="ts">
import { NCheckbox, NCheckboxGroup, NSpace } from 'naive-ui'
import type { CapabilityOption } from '../modelCapabilities'

defineProps<{ modelValue: string[]; options: CapabilityOption[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()
function update(value: Array<string | number>) { emit('update:modelValue', value.map(String)) }
</script>

<style scoped>
.capability-checkbox-group { width: 100%; }
</style>
