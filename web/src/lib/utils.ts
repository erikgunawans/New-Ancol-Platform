import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getScoreColor(score: number): string {
  if (score >= 90) return "text-green-600 bg-green-50";
  if (score >= 80) return "text-blue-600 bg-blue-50";
  if (score >= 70) return "text-amber-600 bg-amber-50";
  if (score >= 60) return "text-orange-600 bg-orange-50";
  return "text-red-600 bg-red-50";
}

export function getScoreGrade(score: number): string {
  if (score >= 90) return "A";
  if (score >= 80) return "B";
  if (score >= 70) return "C";
  if (score >= 60) return "D";
  return "F";
}

export function getScoreLabel(score: number): string {
  if (score >= 90) return "Sangat Baik";
  if (score >= 80) return "Baik";
  if (score >= 70) return "Cukup";
  if (score >= 60) return "Kurang";
  return "Tidak Memenuhi";
}

export function getSeverityColor(severity: string): string {
  switch (severity) {
    case "critical": return "text-red-700 bg-red-100";
    case "high": return "text-orange-700 bg-orange-100";
    case "medium": return "text-amber-700 bg-amber-100";
    case "low": return "text-green-700 bg-green-100";
    default: return "text-gray-700 bg-gray-100";
  }
}

export function getStatusColor(status: string): string {
  if (status === "complete") return "text-green-700 bg-green-100";
  if (status === "failed") return "text-red-700 bg-red-100";
  if (status === "rejected") return "text-red-700 bg-red-100";
  if (status.startsWith("hitl_")) return "text-amber-700 bg-amber-100";
  return "text-blue-700 bg-blue-100";
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("id-ID", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}
