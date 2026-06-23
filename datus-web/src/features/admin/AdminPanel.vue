<script setup lang="ts">
import { onMounted } from "vue"
import { RefreshCwIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAuditLogs } from "@/composables/useAuditLogs"
import { useRoleManager } from "@/composables/useRoleManager"
import { useUserManager } from "@/composables/useUserManager"

const users = useUserManager()
const roles = useRoleManager()
const audits = useAuditLogs()

function loadAll() {
  void users.loadUsers()
  void roles.loadRoles()
  void audits.loadActionTypes()
  void audits.loadLogs()
}

onMounted(loadAll)
</script>

<template>
  <section class="min-h-0 flex-1 overflow-y-auto p-4">
    <Tabs
      default-value="users"
      class="flex flex-col gap-4"
    >
      <div class="flex items-center gap-3">
        <TabsList>
          <TabsTrigger value="users">用户</TabsTrigger>
          <TabsTrigger value="roles">角色</TabsTrigger>
          <TabsTrigger value="audit">审计</TabsTrigger>
        </TabsList>
        <Button
          variant="outline"
          size="sm"
          @click="loadAll"
        >
          <RefreshCwIcon data-icon="inline-start" />
          刷新
        </Button>
      </div>

      <TabsContent value="users">
        <Card>
          <CardHeader>
            <CardTitle>用户管理</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User ID</TableHead>
                  <TableHead>姓名</TableHead>
                  <TableHead>部门</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>角色</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow
                  v-for="user in users.users.value"
                  :key="user.user_id"
                >
                  <TableCell class="font-medium">{{ user.user_id }}</TableCell>
                  <TableCell>{{ user.realname || user.username || "-" }}</TableCell>
                  <TableCell>{{ user.department || "-" }}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{{ user.status }}</Badge>
                  </TableCell>
                  <TableCell>{{ user.roles?.join(", ") || "-" }}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="roles">
        <Card>
          <CardHeader>
            <CardTitle>角色管理</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>编码</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead>用户数</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow
                  v-for="role in roles.roles.value"
                  :key="role.id"
                >
                  <TableCell class="font-medium">{{ role.role_code }}</TableCell>
                  <TableCell>{{ role.role_name }}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{{ role.role_type }}</Badge>
                  </TableCell>
                  <TableCell>{{ role.user_count }}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="audit">
        <Card>
          <CardHeader>
            <CardTitle>审计日志</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>时间</TableHead>
                  <TableHead>操作人</TableHead>
                  <TableHead>动作</TableHead>
                  <TableHead>目标</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow
                  v-for="log in audits.logs.value"
                  :key="log.id"
                >
                  <TableCell>{{ audits.formatDateTime(log.created_at) }}</TableCell>
                  <TableCell>{{ log.operator_name || log.operator_id || "-" }}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{{ audits.getActionText(log.action) }}</Badge>
                  </TableCell>
                  <TableCell>{{ log.target_name || log.target_id || "-" }}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  </section>
</template>
