use std::collections::HashMap;

pub fn group_anagrams(words: Vec<String>) -> Vec<Vec<String>> {
    let mut groups: Vec<Vec<String>> = Vec::new();
    let mut key_to_index: HashMap<Vec<char>, usize> = HashMap::new();

    for word in words {
        let mut key: Vec<char> = word.chars().collect();
        key.sort_unstable();

        if let Some(&index) = key_to_index.get(&key) {
            groups[index].push(word);
        } else {
            let index = groups.len();
            groups.push(vec![word]);
            key_to_index.insert(key, index);
        }
    }

    groups
}
