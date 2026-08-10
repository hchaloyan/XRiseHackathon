/**
 * Mirrors backend/app/schemas.py. Kept in sync BY HAND.
 *
 * Same two rules as the Python side (spec 4.1):
 *   - computed fields come from pandas and are always present
 *   - generated fields come from the LLM and are always `| null`
 *
 * Wire format is camelCase.
 */

export {}
