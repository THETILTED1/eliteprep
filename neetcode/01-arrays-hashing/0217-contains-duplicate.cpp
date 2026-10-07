// @title 0217-contains-duplicate [Easy]

// @star yes

// @related 0242-valid-anagram, 0049-group-anagrams

// @solution O(N) time O(N) space
// @optimal yes
// @patterns hashing
// @primary
//
/*
We load every character into the hash set.
If we try to insert it again, it fails, so return
*/

class Solution {
public:
    bool containsDuplicate(vector<int>& nums) {
        unordered_set<int> seen{};
        for (int k : nums) {
            if (seen.contains(k))
                return true;
            seen.insert(k);
        }
        return false;
    }
};
// @end

// @solution O(N log N) time O(1) space
// @optimal no time O(N)
// @patterns sorting
//
// Space-efficient in-place solution
struct Compare {
    bool operator()(int a, int b) const { return a < b; }
};

class Solution {
public:
    bool containsDuplicate(vector<int>& nums) {
        sort(nums.begin(), nums.end(), Compare{});
        for (size_t i = 1; i < nums.size(); ++i)
            if (nums[i] == nums[i - 1])
                return true;
        return false;
    }
};
// @end
