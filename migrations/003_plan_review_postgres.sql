-- Add review prompts without rewriting any saved prep or end-of-day notes.
ALTER TABLE days ADD COLUMN IF NOT EXISTS plan_followed TEXT;
ALTER TABLE days ADD COLUMN IF NOT EXISTS tomorrow_change TEXT;
