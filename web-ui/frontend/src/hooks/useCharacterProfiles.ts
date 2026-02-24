import { useQuery } from "@tanstack/react-query";
import { characterProfiles, type CharacterProfile } from "../api/client";

/**
 * Fetches character profiles and provides O(1) lookup by personality.
 */
export function useCharacterProfiles() {
  return useQuery({
    queryKey: ["characterProfiles"],
    queryFn: characterProfiles.list,
    staleTime: 5 * 60 * 1000,
    select: (data) => {
      const map = new Map<string, CharacterProfile>();
      for (const p of data) {
        map.set(p.personality, p);
      }
      return map;
    },
  });
}
