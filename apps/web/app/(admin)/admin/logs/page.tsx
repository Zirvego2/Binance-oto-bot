"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import { AdminPageHeader, AdminSectionCard } from "@/components/admin/admin-ui";
import { PaginationBar } from "@/components/shared/pagination-bar";
import { logsApi } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const SEVERITY_VARIANT: Record<string, "destructive" | "warning" | "outline" | "secondary"> = {
  CRITICAL: "destructive",
  HIGH: "destructive",
  MEDIUM: "warning",
  LOW: "outline",
  INFO: "secondary",
};

export default function AdminLogsPage() {
  const [botEventsPage, setBotEventsPage] = React.useState(1);
  const [auditPage, setAuditPage] = React.useState(1);
  const [riskPage, setRiskPage] = React.useState(1);

  const { data: botEvents } = useQuery({
    queryKey: ["admin", "logs", "bot-events", botEventsPage],
    queryFn: () => logsApi.botEvents({ page: botEventsPage, page_size: 30 }),
  });
  const { data: auditLogs } = useQuery({
    queryKey: ["admin", "logs", "audit", auditPage],
    queryFn: () => logsApi.auditLogs({ page: auditPage, page_size: 30 }),
  });
  const { data: riskEvents } = useQuery({
    queryKey: ["admin", "logs", "risk", riskPage],
    queryFn: () => logsApi.riskEvents({ page: riskPage, page_size: 30 }),
  });

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Platform Loglari"
        description="Tum musteriler icin bot olaylari, denetim kayitlari ve risk olaylari — yalnizca platform yoneticisi."
      />

      <Tabs defaultValue="bot-events">
        <TabsList>
          <TabsTrigger value="bot-events">Bot Olaylari</TabsTrigger>
          <TabsTrigger value="risk-events">Risk Olaylari</TabsTrigger>
          <TabsTrigger value="audit">Denetim Kayitlari</TabsTrigger>
        </TabsList>

        <TabsContent value="bot-events">
          <AdminSectionCard title="Bot Olaylari" noPadding contentClassName="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Olay Turu</TableHead>
                  <TableHead>Mesaj</TableHead>
                  <TableHead>Mod</TableHead>
                  <TableHead>Zaman</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(botEvents?.items.length ?? 0) === 0 && (
                  <TableRow>
                    <TableCell colSpan={4} className="py-6 text-center text-muted-foreground">
                      Kayit bulunamadi
                    </TableCell>
                  </TableRow>
                )}
                {botEvents?.items.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell>
                      <Badge variant="outline">{e.event_type}</Badge>
                    </TableCell>
                    <TableCell className="text-sm">{e.message}</TableCell>
                    <TableCell className="text-xs uppercase text-muted-foreground">{e.bot_mode ?? "-"}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{formatDateTime(e.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {botEvents && (
              <PaginationBar
                page={botEvents.page}
                totalPages={botEvents.total_pages}
                total={botEvents.total}
                onPageChange={setBotEventsPage}
              />
            )}
          </AdminSectionCard>
        </TabsContent>

        <TabsContent value="risk-events">
          <AdminSectionCard title="Risk Olaylari" noPadding contentClassName="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Onem</TableHead>
                  <TableHead>Olay Turu</TableHead>
                  <TableHead>Sembol</TableHead>
                  <TableHead>Mesaj</TableHead>
                  <TableHead>Zaman</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(riskEvents?.items.length ?? 0) === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="py-6 text-center text-muted-foreground">
                      Kayit bulunamadi
                    </TableCell>
                  </TableRow>
                )}
                {riskEvents?.items.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell>
                      <Badge variant={SEVERITY_VARIANT[e.severity] ?? "outline"}>{e.severity}</Badge>
                    </TableCell>
                    <TableCell className="text-xs">{e.event_type}</TableCell>
                    <TableCell className="font-medium">{e.symbol ?? "-"}</TableCell>
                    <TableCell className="text-sm">{e.message}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{formatDateTime(e.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {riskEvents && (
              <PaginationBar
                page={riskEvents.page}
                totalPages={riskEvents.total_pages}
                total={riskEvents.total}
                onPageChange={setRiskPage}
              />
            )}
          </AdminSectionCard>
        </TabsContent>

        <TabsContent value="audit">
          <AdminSectionCard title="Denetim Kayitlari" noPadding contentClassName="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Islem</TableHead>
                  <TableHead>Varlik Turu</TableHead>
                  <TableHead>Varlik ID</TableHead>
                  <TableHead>IP</TableHead>
                  <TableHead>Zaman</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(auditLogs?.items.length ?? 0) === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="py-6 text-center text-muted-foreground">
                      Kayit bulunamadi
                    </TableCell>
                  </TableRow>
                )}
                {auditLogs?.items.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell>
                      <Badge variant="outline">{e.action}</Badge>
                    </TableCell>
                    <TableCell className="text-xs">{e.entity_type}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{e.entity_id ?? "-"}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{e.ip_address ?? "-"}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{formatDateTime(e.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {auditLogs && (
              <PaginationBar
                page={auditLogs.page}
                totalPages={auditLogs.total_pages}
                total={auditLogs.total}
                onPageChange={setAuditPage}
              />
            )}
          </AdminSectionCard>
        </TabsContent>
      </Tabs>
    </div>
  );
}
