#!/bin/bash
# Phase 2: Add caching layer to Owner queries
# This simulates a performance optimization where direct DB queries are replaced with cached lookups

set -e

REPO_DIR="/tmp/spring-petclinic"

cd "$REPO_DIR"

echo "=== Phase 2: Adding OwnerService with caching layer ==="

# Step 1: Create OwnerService.java
cat > src/main/java/org/springframework/samples/petclinic/owner/OwnerService.java << 'EOF'
/*
 * Copyright 2012-2025 the original author or authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.springframework.samples.petclinic.owner;

import java.util.Optional;

import org.springframework.cache.CacheManager;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Service;

/**
 * Service layer for Owner operations with caching support.
 * This layer was added as a performance optimization to reduce direct database queries.
 * 
 * @author TMF Experiment Team
 */
@Service
public class OwnerService {

	private final OwnerRepository ownerRepository;
	private final CacheManager cacheManager;

	public OwnerService(OwnerRepository ownerRepository, CacheManager cacheManager) {
		this.ownerRepository = ownerRepository;
		this.cacheManager = cacheManager;
	}

	/**
	 * Find owner by id with caching.
	 * Cache is automatically populated on first access.
	 * Subsequent calls return cached value until evicted.
	 */
	@Cacheable(value = "owners", key = "#id")
	public Optional<Owner> findById(Integer id) {
		return ownerRepository.findById(id);
	}

	/**
	 * Evict owner from cache.
	 * IMPORTANT: Must be called after any operation that modifies owner or related data
	 * (e.g., adding/updating/deleting pets) to ensure cache consistency.
	 */
	public void evictOwnerCache(Integer ownerId) {
		if (cacheManager.getCache("owners") != null) {
			cacheManager.getCache("owners").evict(ownerId);
		}
	}

	/**
	 * Delegate method for saving owner data.
	 * Automatically evicts cache after save.
	 */
	public Owner saveAndFlush(Owner owner) {
		Owner saved = ownerRepository.saveAndFlush(owner);
		evictOwnerCache(saved.getId());
		return saved;
	}

}
EOF

echo "✓ Created OwnerService.java"

# Step 2: Backup original PetController
cp src/main/java/org/springframework/samples/petclinic/owner/PetController.java \
   src/main/java/org/springframework/samples/petclinic/owner/PetController.java.backup

# Step 3: Modify PetController to use OwnerService instead of OwnerRepository
sed -i 's/private final OwnerRepository owners;/private final OwnerService ownerService;/g' \
    src/main/java/org/springframework/samples/petclinic/owner/PetController.java

sed -i 's/public PetController(OwnerRepository owners, PetTypeRepository types) {/public PetController(OwnerService ownerService, PetTypeRepository types) {/g' \
    src/main/java/org/springframework/samples/petclinic/owner/PetController.java

sed -i 's/this\.owners = owners;/this.ownerService = ownerService;/g' \
    src/main/java/org/springframework/samples/petclinic/owner/PetController.java

sed -i 's/this\.owners\.findById/this.ownerService.findById/g' \
    src/main/java/org/springframework/samples/petclinic/owner/PetController.java

sed -i 's/this\.owners\.saveAndFlush/this.ownerService.saveAndFlush/g' \
    src/main/java/org/springframework/samples/petclinic/owner/PetController.java

echo "✓ Modified PetController to use OwnerService"

# Step 4: Add cache eviction in processUpdateForm (critical for Phase 3 test)
# Insert before the redirectAttributes line in processUpdateForm
sed -i '/redirectAttributes.addFlashAttribute("message", "Pet details has been edited");/i \
\t\t// Pet changes affect owner details page cache - must evict to ensure consistency\
\t\townerService.evictOwnerCache(owner.getId());' \
    src/main/java/org/springframework/samples/petclinic/owner/PetController.java

echo "✓ Added cache eviction in processUpdateForm"

# Step 5: Git commit the changes
git add -A
git commit -m "feat: Add caching layer for Owner queries

- Create OwnerService with @Cacheable support
- Migrate PetController from direct OwnerRepository to OwnerService
- Add cache eviction in pet update flow to ensure consistency

This optimization reduces database load for owner detail page lookups.
IMPORTANT: Any operation that modifies owner or pet data must call
ownerService.evictOwnerCache() to maintain cache consistency."

echo ""
echo "=== Phase 2 Complete ==="
echo "Changed files:"
git show --name-status --pretty=format: HEAD
echo ""
echo "Changed functions (TMF would detect these):"
echo "  - PetController.PetController() [constructor signature changed]"
echo "  - PetController.findOwner() [now calls ownerService]"
echo "  - PetController.findPet() [now calls ownerService]"
echo "  - PetController.processCreationForm() [now calls ownerService]"
echo "  - PetController.processUpdateForm() [now calls ownerService + evictOwnerCache]"
echo "  - PetController.updatePetDetails() [now calls ownerService]"
echo "  + OwnerService [NEW FILE - all methods are new]"
