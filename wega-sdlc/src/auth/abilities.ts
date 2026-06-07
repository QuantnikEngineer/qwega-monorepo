/**
 * CASL Abilities
 *
 * Frontend permission rule engine for UX gating.
 * Backend remains the source of truth for authorization.
 */

import { createContext, useContext } from 'react';
import { AbilityBuilder, createMongoAbility, MongoAbility } from '@casl/ability';
import { createContextualCan } from '@casl/react';

export type AppAbility = MongoAbility;

export function defineAbilitiesFor(capabilities: string[]): AppAbility {
  const { can, build } = new AbilityBuilder<AppAbility>(createMongoAbility);

  capabilities.forEach((capability) => {
    const [resource, action] = capability.split(':');
    if (resource && action) {
      can(action, resource);
    }
  });

  return build();
}

export function createDefaultAbility(): AppAbility {
  return createMongoAbility([]);
}

// React context for CASL ability instance
export const AbilityContext = createContext<AppAbility>(createMongoAbility([]));

// Pre-configured <Can> component bound to AbilityContext (D-19)
export const Can = createContextualCan(AbilityContext.Consumer);

// Convenience hook for imperative capability checks
export function useAbility(): AppAbility {
  return useContext(AbilityContext);
}
