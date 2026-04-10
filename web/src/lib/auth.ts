import type { UserRole } from "@/types";

// Role-based route access control
const ROUTE_PERMISSIONS: Record<string, UserRole[]> = {
  "/upload": ["corp_secretary", "admin"],
  "/documents": ["corp_secretary", "internal_auditor", "admin"],
  "/review": ["corp_secretary", "internal_auditor", "legal_compliance", "admin"],
  "/scorecard": ["komisaris", "internal_auditor", "admin"],
  "/reports": ["corp_secretary", "internal_auditor", "komisaris", "legal_compliance", "admin"],
  "/batch": ["corp_secretary", "admin"],
  "/regulations": ["legal_compliance", "admin"],
  "/audit-trail": ["internal_auditor", "admin"],
};

export function canAccessRoute(role: UserRole, path: string): boolean {
  const segment = "/" + path.split("/").filter(Boolean)[0];
  const allowed = ROUTE_PERMISSIONS[segment];
  if (!allowed) return true; // No restriction = accessible
  return allowed.includes(role);
}

export function getDefaultRoute(role: UserRole): string {
  switch (role) {
    case "corp_secretary": return "/upload";
    case "internal_auditor": return "/review";
    case "komisaris": return "/scorecard";
    case "legal_compliance": return "/regulations";
    case "admin": return "/";
    default: return "/";
  }
}
