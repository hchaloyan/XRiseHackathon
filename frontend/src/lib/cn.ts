import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Merge conditional classes, last Tailwind utility wins. */
export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs))
