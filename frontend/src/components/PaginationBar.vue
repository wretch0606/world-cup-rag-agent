<template>
  <nav v-if="totalPages > 1" class="pagination-bar" aria-label="比赛分页">
    <button type="button" :disabled="page <= 1" @click="emit('prev')">
      {{ labels.prev }}
    </button>
    <span class="page-info">{{ labels.pageInfo(page, totalPages, total) }}</span>
    <button type="button" :disabled="page >= totalPages" @click="emit('next')">
      {{ labels.next }}
    </button>
  </nav>
</template>

<script setup lang="ts">
defineProps<{
  page: number
  totalPages: number
  total: number
  labels: {
    prev: string
    next: string
    pageInfo: (page: number, totalPages: number, total: number) => string
  }
}>()

const emit = defineEmits<{
  prev: []
  next: []
}>()
</script>

<style scoped>
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  padding: 6px 0;
}

.pagination-bar button {
  padding: 6px 16px;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  background: #fff;
  color: #555;
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.12s, color 0.12s;
}

.pagination-bar button:hover:not(:disabled) {
  border-color: #4a90d9;
  color: #4a90d9;
}

.pagination-bar button:disabled {
  color: #ccc;
  cursor: not-allowed;
  border-color: #eee;
}

.page-info {
  color: #888;
  font-size: 13px;
  font-weight: 500;
}
</style>
