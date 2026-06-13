/**
 * PlatformServicesPanel
 *
 * SuperAdmin-only dialog for managing the platform service registry.
 * Lists all registered services with enable/disable toggles and
 * an inline form to register new services.
 *
 * GAP-04 Task 2: Platform service registry UI.
 */

import { useState, useMemo } from 'react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '../../components/ui/sheet';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import { ScrollArea } from '../../components/ui/scroll-area';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import { Switch } from '../../components/ui/switch';
import {
  Search,
  Plus,
  AlertTriangle,
  Server,
  X,
} from 'lucide-react';
import { toast } from 'sonner';

import { useServices, useCreateService, useUpdateService } from '../hooks/useServices';
import type { PlatformService } from '../api/adminApi';

interface PlatformServicesPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  ALM: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  SCM: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  CI: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  CD: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  CQ: 'bg-red-500/10 text-red-400 border-red-500/20',
  WIKI: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
};

export function PlatformServicesPanel({ open, onOpenChange }: PlatformServicesPanelProps) {
  const { data, isLoading, isError } = useServices();
  const createMutation = useCreateService();
  const updateMutation = useUpdateService();

  const [search, setSearch] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [newService, setNewService] = useState({
    tool_id: '',
    name: '',
    description: '',
    category: '',
    icon: '',
  });

  const services = data?.services ?? [];

  const filtered = useMemo(() => {
    if (!search) return services;
    const q = search.toLowerCase();
    return services.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.toolId.toLowerCase().includes(q) ||
        (s.category ?? '').toLowerCase().includes(q)
    );
  }, [services, search]);

  const handleToggle = (service: PlatformService) => {
    updateMutation.mutate(
      { serviceId: service.id, data: { enabled: !service.enabled } },
      {
        onSuccess: () =>
          toast.success(`${service.name} ${service.enabled ? 'disabled' : 'enabled'}`),
        onError: (err) =>
          toast.error(err.message),
      }
    );
  };

  const handleCreate = () => {
    if (!newService.tool_id.trim() || !newService.name.trim()) {
      toast.error('Tool ID and Name are required');
      return;
    }
    createMutation.mutate(
      {
        tool_id: newService.tool_id.trim(),
        name: newService.name.trim(),
        description: newService.description.trim() || undefined,
        category: newService.category.trim() || undefined,
        icon: newService.icon.trim() || undefined,
      },
      {
        onSuccess: () => {
          toast.success(`Service "${newService.name}" registered`);
          setNewService({ tool_id: '', name: '', description: '', category: '', icon: '' });
          setShowAddForm(false);
        },
        onError: (err) => toast.error(err.message),
      }
    );
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="sm:max-w-5xl flex flex-col gap-0 p-0">
        <SheetHeader className="px-6 pt-6 pb-4 flex-shrink-0">
          <SheetTitle className="flex items-center gap-2 text-base">
            <Server className="w-4 h-4 text-[#746FA7]" />
            Platform Service Registry
          </SheetTitle>
          <SheetDescription className="text-xs">
            Manage platform-level services available to all projects. Toggle services on/off or register new integrations.
          </SheetDescription>
        </SheetHeader>

        <div className="px-6 pb-3 flex items-center gap-2 flex-shrink-0">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
            <Input
              placeholder="Search services..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-8 text-xs"
            />
          </div>
          <Button
            size="sm"
            variant={showAddForm ? 'secondary' : 'default'}
            className="h-8 text-xs gap-1"
            onClick={() => setShowAddForm(!showAddForm)}
          >
            {showAddForm ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
            {showAddForm ? 'Cancel' : 'Add Service'}
          </Button>
        </div>

        {/* Add new service form */}
        {showAddForm && (
          <div className="px-6 pb-3 border-b">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Tool ID *</Label>
                <Input
                  placeholder="e.g. azure-devops"
                  value={newService.tool_id}
                  onChange={(e) => setNewService({ ...newService, tool_id: e.target.value })}
                  className="h-8 text-xs mt-1"
                />
              </div>
              <div>
                <Label className="text-xs">Name *</Label>
                <Input
                  placeholder="e.g. Azure DevOps"
                  value={newService.name}
                  onChange={(e) => setNewService({ ...newService, name: e.target.value })}
                  className="h-8 text-xs mt-1"
                />
              </div>
              <div>
                <Label className="text-xs">Category</Label>
                <Input
                  placeholder="e.g. ALM, SCM, CI, CD, CQ, WIKI"
                  value={newService.category}
                  onChange={(e) => setNewService({ ...newService, category: e.target.value })}
                  className="h-8 text-xs mt-1"
                />
              </div>
              <div>
                <Label className="text-xs">Icon (emoji)</Label>
                <Input
                  placeholder="e.g. 🔧"
                  value={newService.icon}
                  onChange={(e) => setNewService({ ...newService, icon: e.target.value })}
                  className="h-8 text-xs mt-1"
                />
              </div>
              <div className="col-span-2">
                <Label className="text-xs">Description</Label>
                <Input
                  placeholder="Short description of the service"
                  value={newService.description}
                  onChange={(e) => setNewService({ ...newService, description: e.target.value })}
                  className="h-8 text-xs mt-1"
                />
              </div>
            </div>
            <div className="flex justify-end mt-3">
              <Button
                size="sm"
                className="h-8 text-xs"
                onClick={handleCreate}
                disabled={createMutation.isPending}
              >
                {createMutation.isPending ? 'Registering...' : 'Register Service'}
              </Button>
            </div>
          </div>
        )}

        {/* Service list */}
        <ScrollArea className="flex-1 min-h-0 px-6">
          {isLoading ? (
            <div className="space-y-3 py-4">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : isError ? (
            <div className="flex flex-col items-center justify-center py-12 gap-2 text-muted-foreground">
              <AlertTriangle className="w-8 h-8" />
              <p className="text-xs">Failed to load services</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-2 text-muted-foreground">
              <Server className="w-8 h-8" />
              <p className="text-xs">{search ? 'No services match your search' : 'No services registered'}</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs w-10"></TableHead>
                  <TableHead className="text-xs">Service</TableHead>
                  <TableHead className="text-xs">Category</TableHead>
                  <TableHead className="text-xs text-center">Enabled</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((service) => (
                  <TableRow key={service.id}>
                    <TableCell className="text-center text-base">
                      {service.icon || '🔧'}
                    </TableCell>
                    <TableCell>
                      <div>
                        <p className="text-xs font-medium">{service.name}</p>
                        <p className="text-[10px] text-muted-foreground">{service.toolId}</p>
                        {service.description && (
                          <p className="text-[10px] text-muted-foreground mt-0.5">{service.description}</p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {service.category ? (
                        <Badge
                          variant="secondary"
                          className={`text-[10px] font-medium rounded-md px-2 py-0.5 border ${CATEGORY_COLORS[service.category] ?? 'bg-muted text-muted-foreground'}`}
                        >
                          {service.category}
                        </Badge>
                      ) : (
                        <span className="text-[10px] text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-center">
                      <Switch
                        checked={service.enabled}
                        onCheckedChange={() => handleToggle(service)}
                        disabled={updateMutation.isPending}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </ScrollArea>

        <div className="px-6 py-3 border-t text-[10px] text-muted-foreground">
          {services.length} service{services.length !== 1 ? 's' : ''} registered
          {services.length > 0 && ` · ${services.filter((s) => s.enabled).length} enabled`}
        </div>
      </SheetContent>
    </Sheet>
  );
}
